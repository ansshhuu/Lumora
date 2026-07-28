"""
Week 3 Day 2 — ReAct agent wiring.

Builds a create_react_agent from the Day 1-2 tools and runs it with a hard
cap on tool-call loops.
"""
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from lumora.agent.tools import fetch_file, find_function, get_repo_structure, search_code

MODEL_NAME = "openai/gpt-oss-120b"
RECURSION_LIMIT = 10

TOOLS = [search_code, fetch_file, get_repo_structure, find_function]

llm = ChatGroq(model=MODEL_NAME)
agent = create_react_agent(llm, TOOLS)


def ask(question: str) -> str:
    """
    Run the ReAct agent on a single natural-language question about the
    indexed repository and return its final text answer.

    Enforces RECURSION_LIMIT as a hard cap on the agent's tool-call loop so a
    confused agent can't run away. Wraps the underlying LLM/tool-call chain
    in a try/except so a timeout or API failure returns a readable message
    instead of crashing the caller.
    """
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": RECURSION_LIMIT},
        )
    except Exception as e:
        return f"Error: agent failed to answer ({e})."

    messages = result.get("messages", [])
    if not messages:
        return "Error: agent returned no response."

    return messages[-1].content
