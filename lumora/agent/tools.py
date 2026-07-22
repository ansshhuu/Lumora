
from langchain_core.tools import tool

from lumora.embeddings.search import search_code as search_codebase

MAX_CODE_CHARS = 500


def _format_hit(hit: dict) -> str:
    payload = hit.get("payload") or {}
    name = payload.get("name", "unknown")
    kind = payload.get("type", "code")
    file_path = payload.get("file_path", "unknown file")
    start_line = payload.get("start_line")
    end_line = payload.get("end_line")
    location = f"{file_path}:{start_line}-{end_line}" if start_line and end_line else file_path

    code = payload.get("code", "")
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS] + "... [truncated]"

    return (
        f"{kind} `{name}` ({location})\n"
        f"```python\n{code}\n```"
    )


@tool
def search_code(query: str) -> str:
    """
    Search the indexed codebase for functions, classes, and methods that are
    semantically relevant to a natural-language query.

    Use this tool whenever you need to find WHERE something is implemented,
    HOW a specific behavior works, or WHICH functions/classes relate to a
    concept (e.g. "how does session handle redirects", "where is auth
    validated"). Do not use it for questions unrelated to the codebase.

    Args:
        query: A natural-language description of what you're looking for.

    Returns:
        A readable, formatted string listing the top matching code chunks
        (function/class name, file path with line range, and a truncated
        code snippet). Returns "No results found." if nothing matches, or
        an error message string if the search backend is unavailable.
    """
    try:
        results = search_codebase(query)
    except Exception as e:
        return f"Error: code search failed ({e})."

    if not results:
        return "No results found."

    return "\n\n".join(_format_hit(hit) for hit in results)
