"""
Week 3 Day 2/4 — ReAct agent wiring.

Builds a create_react_agent from the Day 1-2 tools and streams its reasoning
(tool calls + tool results) as it runs, with a hard cap on tool-call loops.
"""
from pathlib import Path

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
        llm = ChatGroq(model=MODEL_NAME)
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


def ask(question: str, collection: str, repo_root: str) -> str:
    """
    Run the ReAct agent on a single natural-language question about the
    indexed repository, streaming and printing each reasoning step (tool
    calls and tool results) as it happens, and return the final text answer.

    `collection` is the Qdrant collection name for the indexed repo.
    `repo_root` is the absolute filesystem path to the cloned repository.

    Enforces RECURSION_LIMIT as a hard cap on the agent's tool-call loop so a
    confused agent can't run away. Wraps the underlying LLM/tool-call chain
    in a try/except so a timeout or API failure returns a readable message
    instead of crashing the caller.
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
                if node == "agent" and node_update.get("messages"):
                    final_message = node_update["messages"][-1]
    except GraphRecursionError:
        # The agent exhausted its tool-call budget without reaching a final
        # answer.  Return an honest, actionable message rather than letting
        # LangGraph's internal "need more steps" string leak to the user.
        return _STEP_LIMIT_RESPONSE
    except Exception as e:
        return f"Error: agent failed to answer ({e})."

    if final_message is None:
        return "Error: agent returned no response."

    # Dual-defence: LangGraph 1.2.9 emits the step-limit sentinel as the last
    # stream message *before* raising GraphRecursionError.  The exception catch
    # above handles the normal path; this guard handles the edge case where
    # the exception does not propagate through the generator (e.g. it gets
    # consumed internally) but the poisoned content still lands in final_message.
    content = final_message.content or ""
    if _LANGGRAPH_STEP_LIMIT_SENTINEL in content.lower():
        return _STEP_LIMIT_RESPONSE

    return content
