
import os
from contextvars import ContextVar
from pathlib import Path

from langchain_core.tools import tool
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText

from lumora.embeddings.search import search_code as search_codebase
from lumora.embeddings.qdrant_store import client as qdrant_client
from lumora.ingestion.walker import walk_files

MAX_CODE_CHARS = 2000
MAX_FILE_BYTES = 50 * 1024

# Per-request context variables — set by ask() before each agent invocation so
# the @tool functions (whose signatures are controlled by LangGraph) can reach
# the correct collection and filesystem root without changing their LLM-visible
# API.  Falls back to the old env-var / hardcoded values so unit tests that
# don't call set_request_context continue to work.
_collection_ctx: ContextVar[str] = ContextVar(
    "_collection_ctx",
    default=os.getenv("LUMORA_DEFAULT_COLLECTION", "requests_repo"),
)
_repo_root_ctx: ContextVar[Path] = ContextVar(
    "_repo_root_ctx",
    default=Path(os.getenv("LUMORA_REPO_ROOT", "test_repos/requests")).resolve(),
)


def set_request_context(collection: str, repo_root: Path) -> None:
    """Called once per ask() invocation to bind the correct collection and repo
    root into the current thread's context variables before the agent streams."""
    _collection_ctx.set(collection)
    _repo_root_ctx.set(repo_root)


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
    Semantically searches the codebase.
    Use this tool when the query is conceptual, vague, or describes logic
    (e.g., 'where is the authentication handled?', 'how does retry logic work?').
    It returns code snippets that match the meaning of the query.
    """
    collection = _collection_ctx.get()
    try:
        results = search_codebase(query, collection_name=collection)
    except Exception as e:
        return f"Error: code search failed ({e})."

    if not results:
        return "No results found."

    return "\n\n".join(_format_hit(hit) for hit in results)


@tool
def fetch_file(file_path: str) -> str:
    """
    Reads and returns the entire content of a specific file.
    Use this tool ONLY when you know the exact file path (e.g., 'src/main.py').
    Helpful when you need full context beyond just a small code snippet.
    """
    repo_root = _repo_root_ctx.get()
    try:
        candidate = (repo_root / file_path).resolve()
    except Exception as e:
        return f"Error: invalid path ({e})."

    if repo_root != candidate and repo_root not in candidate.parents:
        return f"Error: '{file_path}' is outside the repository root."

    if not candidate.exists() or not candidate.is_file():
        return f"File not found: {file_path}"

    try:
        with open(candidate, "rb") as f:
            data = f.read(MAX_FILE_BYTES + 1)
    except Exception as e:
        return f"Error: could not read file ({e})."

    truncated = len(data) > MAX_FILE_BYTES
    if truncated:
        data = data[:MAX_FILE_BYTES]

    text = data.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n... [truncated, file exceeds {MAX_FILE_BYTES // 1024}KB]"

    return text


@tool
def get_repo_structure(max_depth: int = 3) -> str:
    """
    Returns the directory tree and file structure of the repository.
    Use this tool early in your reasoning when you need a high-level map
    of the project to understand where relevant files might be located.
    """
    repo_root = _repo_root_ctx.get()
    if not repo_root.exists() or not repo_root.is_dir():
        return f"Error: repository root not found at {repo_root}."

    try:
        paths = sorted(walk_files(str(repo_root)))
    except Exception as e:
        return f"Error: failed to walk repository ({e})."

    tree_dirs = set()
    lines = []
    entries = []

    for path in paths:
        rel = path.relative_to(repo_root)
        if len(rel.parts) - 1 > max_depth:
            continue
        entries.append(rel)
        for i in range(1, len(rel.parts)):
            tree_dirs.add(rel.parts[:i])

    all_nodes = sorted(set(tree_dirs) | {e.parts for e in entries})

    for parts in all_nodes:
        depth = len(parts) - 1
        indent = "  " * depth
        name = parts[-1]
        is_dir = tuple(parts) in tree_dirs
        lines.append(f"{indent}{name}/" if is_dir else f"{indent}{name}")

    if not lines:
        return "Repository is empty (or everything was filtered out)."

    return "\n".join(lines)


@tool
def find_function(name: str) -> str:
    """
    Looks up a specific function, class, or method by its name.
    Use this tool when you ALREADY know the exact or partial name of the function
    (e.g., 'retry_request') and need to find which file and lines it is located in.
    Faster and more accurate than semantic search for exact names.
    """
    collection = _collection_ctx.get()
    try:
        exact, _ = qdrant_client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="short_name", match=MatchValue(value=name))]
            ),
            limit=20,
            with_payload=True,
        )
    except Exception as e:
        return f"Error: lookup failed ({e})."

    matches = exact
    if not matches:
        try:
            scanned, _ = qdrant_client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    should=[
                        FieldCondition(key="short_name", match=MatchText(text=name)),
                        FieldCondition(key="name", match=MatchText(text=name))
                    ]
                ),
                limit=20,
                with_payload=True,
            )
            matches = scanned
        except Exception as e:
            return f"Error: fallback lookup failed ({e})."

    if not matches:
        return f"No function or class named '{name}' found."

    lines = []
    for point in matches:
        payload = point.payload or {}
        full_name = payload.get("name", "unknown")
        kind = payload.get("type", "code")
        file_path = payload.get("file_path", "unknown file")
        start_line = payload.get("start_line")
        end_line = payload.get("end_line")
        location = f"{file_path}:{start_line}-{end_line}" if start_line and end_line else file_path
        lines.append(f"{kind} `{full_name}` — {location}")

    return "\n".join(lines)
