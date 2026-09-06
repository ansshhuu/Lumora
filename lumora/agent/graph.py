"""
Week 3 Day 2/4 — ReAct agent wiring.

Builds a create_react_agent from the Day 1-2 tools and streams its reasoning
(tool calls + tool results) as it runs, with a hard cap on tool-call loops.

`ask_stream()` yields those steps as structured event dicts for the SSE
endpoint; `ask()` drains the same generator for callers that only want the
final answer string.
"""
import json
from pathlib import Path
from typing import Iterator

from langchain_groq import ChatGroq
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from lumora.agent.prompts import SYSTEM_PROMPT
from lumora.agent.tools import (
    fetch_file,
    find_function,
    get_repo_structure,
    search_code,
    set_request_context,
)

MODEL_NAME = "openai/gpt-oss-120b"
# Greedy decoding.  The agent's job is to pick tool calls, not to write prose,
# and sampling variance is what produces Groq's `output_parse_failed` 400s --
# the model free-styling reasoning text where a structured call belongs.  This
# narrows that failure mode; _is_parse_failure() still covers the remainder.
#
# Note: langchain_groq rewrites a literal 0 to 1e-8 on the wire, because Groq's
# API rejects zero.  That is still effectively greedy, so the 0 here is honest
# about intent -- don't "fix" the 1e-8 if you see it in a request payload.
TEMPERATURE = 0
# RECURSION_LIMIT caps the agent's tool-call loop.  10 is the LangGraph
# default and keeps Groq free-tier token burn reasonable, but very broad
# questions ("explain the whole repo") may legitimately need more steps.
# Raising to 15 would give the agent more headroom at the cost of ~50% more
# tokens per worst-case query.  Left at 10 for now; revisit if the custom
# recursion-error message fires too often on legitimate questions.
RECURSION_LIMIT = 10
PREVIEW_CHARS = 300

TOOLS = [search_code, fetch_file, get_repo_structure, find_function]

# Sentinel emitted by LangGraph 1.2.9 as the final assistant message content
# immediately before it raises GraphRecursionError.  We check for it so that
# if the exception is somehow swallowed upstream, the poisoned string never
# reaches the caller.
_LANGGRAPH_STEP_LIMIT_SENTINEL = "need more steps"

# Built lazily so importing this module never requires a key. ChatGroq raises
# at construction when GROQ_API_KEY is unset, which previously made the whole
# API package unimportable in CI and unit tests. Mirrors embedder.get_client().
_agent = None


def get_agent():
    """Returns the process-wide ReAct agent, constructing it on first use."""
    global _agent
    if _agent is None:
        llm = ChatGroq(model=MODEL_NAME, temperature=TEMPERATURE)
        _agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)
    return _agent


def _preview(text: str) -> str:
    text = str(text)
    if len(text) > PREVIEW_CHARS:
        return text[:PREVIEW_CHARS] + "... [truncated]"
    return text


def _print(line: str) -> None:
    """Print a trace line, tolerating consoles that can't encode every character."""
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", errors="replace").decode("ascii"))


def _log_step(node: str, update: dict) -> None:
    """Print one step of the agent's reasoning trace (tool call or tool result)."""
    for message in update.get("messages", []):
        if node == "agent":
            for call in getattr(message, "tool_calls", None) or []:
                _print(f"[tool call] {call['name']}({call['args']})")
            if message.content:
                _print(f"[agent] {_preview(message.content)}")
        elif node == "tools":
            tool_name = getattr(message, "name", "unknown_tool")
            _print(f"[tool result] {tool_name} -> {_preview(message.content)}")


_STEP_LIMIT_RESPONSE = (
    "I wasn't able to find a confident answer within the allowed "
    "search steps. Try rephrasing your question to be more specific, "
    "or ask about a narrower part of the codebase."
)

# Groq returns HTTP 400 with this code when the model emits prose where a
# structured tool call was required, e.g. "Let's search for other argparse
# usage." instead of a call.  It is a sampling glitch rather than a problem
# with the question, so the same query often succeeds on a second attempt.
_PARSE_FAILURE_MARKERS = ("output_parse_failed", "failed_generation")

# One extra attempt only.  Each retry costs a full agent run (tokens + latency),
# and a question that trips the parser twice is unlikely to succeed on a third.
MAX_PARSE_RETRIES = 1


def _is_parse_failure(exc: Exception) -> bool:
    """
    True when an exception is Groq's "model output could not be parsed" error.

    Matched on the message text rather than the exception class: the error
    surfaces as a plain BadRequestError whose only distinguishing feature is
    the `output_parse_failed` code in its body, and it reaches us wrapped by
    LangChain, so the concrete type is not a reliable signal.
    """
    text = str(exc).lower()
    return any(marker in text for marker in _PARSE_FAILURE_MARKERS)


def _tool_call_input(args) -> str:
    """Render a tool call's arguments as a short single-line string for the UI."""
    if isinstance(args, dict):
        # Single-argument tools (the common case) read better unwrapped:
        # search_code(query="retry logic") -> "retry logic".
        if len(args) == 1:
            return _preview(str(next(iter(args.values()))))
        return _preview(json.dumps(args, default=str))
    return _preview(str(args))


def _events_for(node: str, update: dict) -> Iterator[dict]:
    """Translate one LangGraph node update into zero or more SSE step events."""
    for message in update.get("messages", []):
        if node == "agent":
            for call in getattr(message, "tool_calls", None) or []:
                yield {
                    "type": "tool_call",
                    "name": call.get("name", "unknown_tool"),
                    "input": _tool_call_input(call.get("args")),
                }
        elif node == "tools":
            yield {
                "type": "tool_result",
                "name": getattr(message, "name", "unknown_tool"),
                "preview": _preview(message.content),
            }


def _final_answer_event(text: str) -> dict:
    """Build the terminal event. Citation is reserved for a later milestone."""
    return {"type": "final_answer", "text": text, "citation": None}


def _ask_once(question: str, collection: str, repo_root: str) -> Iterator[dict]:
    """
    Run the agent once, yielding step events and a terminal `final_answer`.

    Raises rather than yields on a Groq output-parse failure so `ask_stream`
    can retry the attempt; every other error is still turned into a terminal
    event here, because those are not worth a second run.
    """
    # Bind per-request context so all @tool functions operate on this session's
    # collection and repo path, not the module-level defaults.
    set_request_context(collection, Path(repo_root))

    final_message = None
    try:
        for update in get_agent().stream(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": RECURSION_LIMIT},
            stream_mode="updates",
        ):
            for node, node_update in update.items():
                _log_step(node, node_update)
                yield from _events_for(node, node_update)
                if node == "agent" and node_update.get("messages"):
                    final_message = node_update["messages"][-1]
    except GraphRecursionError:
        # The agent exhausted its tool-call budget without reaching a final
        # answer.  Return an honest, actionable message rather than letting
        # LangGraph's internal "need more steps" string leak to the user.
        yield _final_answer_event(_STEP_LIMIT_RESPONSE)
        return
    except Exception as e:
        # Let the caller decide whether this one is worth another attempt.
        if _is_parse_failure(e):
            raise
        yield _final_answer_event(f"Error: agent failed to answer ({e}).")
        return

    if final_message is None:
        yield _final_answer_event("Error: agent returned no response.")
        return

    # Dual-defence: LangGraph 1.2.9 emits the step-limit sentinel as the last
    # stream message *before* raising GraphRecursionError.  The exception catch
    # above handles the normal path; this guard handles the edge case where
    # the exception does not propagate through the generator (e.g. it gets
    # consumed internally) but the poisoned content still lands in final_message.
    content = final_message.content or ""
    if _LANGGRAPH_STEP_LIMIT_SENTINEL in content.lower():
        yield _final_answer_event(_STEP_LIMIT_RESPONSE)
        return

    yield _final_answer_event(content)


def ask_stream(question: str, collection: str, repo_root: str) -> Iterator[dict]:
    """
    Run the ReAct agent on a single question, yielding each reasoning step as a
    structured event dict as it happens, and finally a `final_answer` event.

    Event shapes:
      {"type": "tool_call",    "name": ..., "input": ...}
      {"type": "tool_result",  "name": ..., "preview": ...}
      {"type": "retry",        "reason": ..., "attempt": ...}
      {"type": "final_answer", "text": ..., "citation": None}

    This is the streaming counterpart to `ask()`, which drains this generator.
    Errors are yielded as a terminal `final_answer` carrying the readable
    message rather than raised, so a partially-streamed response always ends
    with a well-formed terminal event instead of a truncated SSE body.

    Groq intermittently fails to parse its own model output into a tool call
    (HTTP 400 `output_parse_failed`).  That is a sampling glitch, not a problem
    with the question, so the attempt is retried once before the error reaches
    the user.  A failure can land after steps have already been streamed, so a
    `retry` event precedes the second attempt to tell the client to discard the
    steps from the abandoned one.

    `collection` is the Qdrant collection name for the indexed repo.
    `repo_root` is the absolute filesystem path to the cloned repository.
    """
    for attempt in range(MAX_PARSE_RETRIES + 1):
        try:
            yield from _ask_once(question, collection, repo_root)
            return
        except Exception as e:
            is_last = attempt == MAX_PARSE_RETRIES
            if is_last:
                _print(f"[parse failure] giving up after {attempt + 1} attempts")
                yield _final_answer_event(f"Error: agent failed to answer ({e}).")
                return

            _print(f"[parse failure] retrying (attempt {attempt + 2})")
            yield {
                "type": "retry",
                "reason": "the model returned unparseable output",
                "attempt": attempt + 2,
            }


def ask(question: str, collection: str, repo_root: str) -> str:
    """
    Run the ReAct agent on a single natural-language question about the
    indexed repository, streaming and printing each reasoning step (tool
    calls and tool results) as it happens, and return the final text answer.

    Thin wrapper over `ask_stream()`: drains the event stream and returns the
    text of the terminal `final_answer` event, so both entry points share one
    implementation of the loop, the step cap and the failure handling.
    """
    text = "Error: agent returned no response."
    for event in ask_stream(question, collection, repo_root):
        if event["type"] == "final_answer":
            text = event["text"]
    return text
