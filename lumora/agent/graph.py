"""
Week 3 Day 2/4 — ReAct agent wiring.

Builds a create_react_agent from the Day 1-2 tools and streams its reasoning
(tool calls + tool results) as it runs, with a hard cap on tool-call loops.
"""
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from lumora.agent.prompts import SYSTEM_PROMPT
from lumora.agent.tools import fetch_file, find_function, get_repo_structure, search_code

MODEL_NAME = "openai/gpt-oss-120b"
RECURSION_LIMIT = 10
PREVIEW_CHARS = 300

TOOLS = [search_code, fetch_file, get_repo_structure, find_function]

llm = ChatGroq(model=MODEL_NAME)
agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)


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


def ask(question: str) -> str:
    """
    Run the ReAct agent on a single natural-language question about the
    indexed repository, streaming and printing each reasoning step (tool
    calls and tool results) as it happens, and return the final text answer.

    Enforces RECURSION_LIMIT as a hard cap on the agent's tool-call loop so a
    confused agent can't run away. Wraps the underlying LLM/tool-call chain
    in a try/except so a timeout or API failure returns a readable message
    instead of crashing the caller.
    """
    final_message = None
    try:
        for update in agent.stream(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": RECURSION_LIMIT},
            stream_mode="updates",
        ):
            for node, node_update in update.items():
                _log_step(node, node_update)
                if node == "agent" and node_update.get("messages"):
                    final_message = node_update["messages"][-1]
    except Exception as e:
        return f"Error: agent failed to answer ({e})."

    if final_message is None:
        return "Error: agent returned no response."

    return final_message.content
