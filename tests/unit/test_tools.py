"""Unit tests for the agent tools.

Every external dependency (Qdrant, Cohere) is mocked. REPO_ROOT is resolved at
import time, so tests point it at a tmp directory via monkeypatch.
"""

import pytest

from lumora.agent import tools
from lumora.agent.tools import (
    MAX_CODE_CHARS,
    MAX_FILE_BYTES,
    _format_hit,
    fetch_file,
    find_function,
    get_repo_structure,
    search_code,
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point REPO_ROOT at an isolated tmp repo and return its path."""
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(tools, "REPO_ROOT", root.resolve())
    return root


def make_hit(**payload):
    """Build a Qdrant-shaped hit dict with sensible defaults."""
    base = {
        "name": "do_thing",
        "type": "function",
        "file_path": "src/app.py",
        "start_line": 10,
        "end_line": 20,
        "code": "def do_thing():\n    pass",
    }
    base.update(payload)
    return {"score": 0.9, "id": 1, "payload": base}


# ================================================================
# fetch_file - path traversal guard
# ================================================================


@pytest.mark.parametrize(
    "evil_path",
    [
        "../../etc/passwd",
        "../../../etc/passwd",
        "../secrets.env",
        "..",
        "../",
        "subdir/../../outside.txt",
    ],
)
def test_fetch_file_rejects_traversal_paths(repo, evil_path):
    result = fetch_file.func(evil_path)

    assert "outside the repository root" in result


def test_fetch_file_rejects_absolute_path_outside_root(repo, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("classified")

    result = fetch_file.func(str(secret))

    assert "outside the repository root" in result
    assert "classified" not in result


def test_traversal_guard_does_not_leak_file_contents(repo, tmp_path):
    """The rejection must not read the target file at all."""
    outside = tmp_path / "outside.txt"
    outside.write_text("SENSITIVE-TOKEN-12345")

    result = fetch_file.func("../outside.txt")

    assert "SENSITIVE-TOKEN-12345" not in result


def test_fetch_file_allows_path_that_traverses_but_stays_inside(repo):
    """A path like sub/../real.py resolves inside the root, so it is permitted."""
    (repo / "real.py").write_text("VALUE = 1")
    (repo / "sub").mkdir()

    result = fetch_file.func("sub/../real.py")

    assert "VALUE = 1" in result


def test_fetch_file_reads_nested_file_inside_root(repo):
    nested = repo / "pkg" / "mod.py"
    nested.parent.mkdir()
    nested.write_text("VALUE = 42")

    assert "VALUE = 42" in fetch_file.func("pkg/mod.py")


# ================================================================
# fetch_file - truncation (Week 3 fix)
# ================================================================


def test_fetch_file_truncates_oversized_content(repo):
    (repo / "big.py").write_bytes(b"a" * (MAX_FILE_BYTES + 5000))

    result = fetch_file.func("big.py")

    assert "[truncated" in result
    assert f"exceeds {MAX_FILE_BYTES // 1024}KB" in result


def test_truncated_body_is_capped_at_the_limit(repo):
    (repo / "big.py").write_bytes(b"a" * (MAX_FILE_BYTES * 2))

    result = fetch_file.func("big.py")
    body = result.split("\n... [truncated")[0]

    assert len(body) == MAX_FILE_BYTES


def test_file_exactly_at_limit_is_not_truncated(repo):
    """Boundary: only content strictly over the cap gets a truncation note."""
    (repo / "exact.py").write_bytes(b"a" * MAX_FILE_BYTES)

    result = fetch_file.func("exact.py")

    assert "[truncated" not in result
    assert len(result) == MAX_FILE_BYTES


def test_small_file_is_returned_whole_without_note(repo):
    # Written as bytes: fetch_file reads binary, so no newline translation.
    (repo / "small.py").write_bytes(b"def tiny():\n    return 1\n")

    result = fetch_file.func("small.py")

    assert result == "def tiny():\n    return 1\n"
    assert "[truncated" not in result


def test_fetch_file_handles_invalid_utf8_without_raising(repo):
    (repo / "bin.py").write_bytes(b"valid \xff\xfe bytes")

    result = fetch_file.func("bin.py")

    assert "valid" in result
    assert "�" in result  # replacement char, decoded with errors="replace"


# ================================================================
# fetch_file - missing files and directories
# ================================================================


def test_fetch_file_missing_file_returns_message_not_exception(repo):
    result = fetch_file.func("does_not_exist.py")

    assert result == "File not found: does_not_exist.py"


def test_fetch_file_missing_nested_file_returns_message(repo):
    result = fetch_file.func("deep/nested/ghost.py")

    assert "File not found" in result


def test_fetch_file_on_directory_returns_not_found(repo):
    (repo / "pkg").mkdir()

    result = fetch_file.func("pkg")

    assert "File not found" in result


def test_fetch_file_read_error_is_caught(repo, monkeypatch):
    (repo / "locked.py").write_text("data")

    def boom(*args, **kwargs):
        raise PermissionError("locked by another process")

    monkeypatch.setattr("builtins.open", boom)
    result = fetch_file.func("locked.py")

    assert "Error: could not read file" in result
    assert "locked by another process" in result


# ================================================================
# get_repo_structure
# ================================================================


def test_repo_structure_lists_files_and_directories(repo):
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x")
    (repo / "README.md").write_text("x")

    result = get_repo_structure.func()

    assert "README.md" in result
    assert "src/" in result
    assert "app.py" in result


def test_repo_structure_indents_by_depth(repo):
    (repo / "src" / "deep").mkdir(parents=True)
    (repo / "src" / "deep" / "mod.py").write_text("x")

    lines = {ln.strip(): ln for ln in get_repo_structure.func().splitlines()}

    assert not lines["src/"].startswith(" ")     # depth 0, no indent
    assert lines["deep/"].startswith("  ")       # depth 1
    assert lines["mod.py"].startswith("    ")    # depth 2


def test_repo_structure_marks_directories_with_trailing_slash(repo):
    (repo / "pkg").mkdir()
    (repo / "pkg" / "file.py").write_text("x")

    result = get_repo_structure.func().splitlines()

    assert any(ln.strip() == "pkg/" for ln in result)
    assert any(ln.strip() == "file.py" for ln in result)


def test_repo_structure_respects_max_depth(repo):
    deep = repo / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "buried.py").write_text("x")
    (repo / "top.py").write_text("x")

    result = get_repo_structure.func(max_depth=1)

    assert "top.py" in result
    assert "buried.py" not in result


def test_repo_structure_deeper_max_depth_includes_more(repo):
    deep = repo / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "found.py").write_text("x")

    assert "found.py" not in get_repo_structure.func(max_depth=0)
    assert "found.py" in get_repo_structure.func(max_depth=5)


def test_repo_structure_skips_junk_directories(repo):
    (repo / ".git").mkdir()
    (repo / ".git" / "config.py").write_text("x")
    (repo / "real.py").write_text("x")

    result = get_repo_structure.func()

    assert "real.py" in result
    assert "config.py" not in result


def test_repo_structure_empty_repo_returns_message(repo):
    result = get_repo_structure.func()

    assert "empty" in result.lower()


def test_repo_structure_missing_root_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "REPO_ROOT", tmp_path / "gone")

    result = get_repo_structure.func()

    assert "Error: repository root not found" in result


def test_repo_structure_walk_failure_is_caught(repo, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("filesystem exploded")

    monkeypatch.setattr(tools, "walk_files", boom)
    result = get_repo_structure.func()

    assert "Error: failed to walk repository" in result


# ================================================================
# search_code - formatting, with Qdrant mocked out
# ================================================================


def test_search_code_formats_hit_with_location(monkeypatch):
    monkeypatch.setattr(tools, "search_codebase", lambda q: [make_hit()])

    result = search_code.func("how does retry work")

    assert "function `do_thing`" in result
    assert "src/app.py:10-20" in result
    assert "```python" in result
    assert "def do_thing():" in result


def test_search_code_passes_query_through_to_backend(monkeypatch):
    captured = {}

    def fake_search(query):
        captured["query"] = query
        return [make_hit()]

    monkeypatch.setattr(tools, "search_codebase", fake_search)
    search_code.func("authentication logic")

    assert captured["query"] == "authentication logic"


def test_search_code_joins_multiple_hits(monkeypatch):
    hits = [make_hit(name="first"), make_hit(name="second")]
    monkeypatch.setattr(tools, "search_codebase", lambda q: hits)

    result = search_code.func("q")

    assert "`first`" in result
    assert "`second`" in result
    assert result.count("```python") == 2


def test_search_code_empty_results_message(monkeypatch):
    monkeypatch.setattr(tools, "search_codebase", lambda q: [])

    assert search_code.func("nothing") == "No results found."


def test_search_code_backend_failure_returns_error_string(monkeypatch):
    def boom(query):
        raise ConnectionError("qdrant unreachable")

    monkeypatch.setattr(tools, "search_codebase", boom)
    result = search_code.func("q")

    assert "Error: code search failed" in result
    assert "qdrant unreachable" in result


def test_search_code_does_not_touch_real_qdrant(mocker):
    """Guard: the mocked path must never reach the real client."""
    spy = mocker.patch.object(tools.qdrant_client, "query_points")
    mocker.patch.object(tools, "search_codebase", return_value=[make_hit()])

    search_code.func("q")

    spy.assert_not_called()


# --- _format_hit directly -------------------------------------------------


def test_format_hit_truncates_long_code():
    long_code = "x" * (MAX_CODE_CHARS + 500)

    result = _format_hit(make_hit(code=long_code))

    assert "... [truncated]" in result
    assert len(result) < len(long_code) + 300


def test_format_hit_keeps_short_code_intact():
    result = _format_hit(make_hit(code="def f(): pass"))

    assert "def f(): pass" in result
    assert "[truncated]" not in result


def test_format_hit_falls_back_when_payload_missing_fields():
    result = _format_hit({"payload": {}})

    assert "unknown" in result
    assert "unknown file" in result


def test_format_hit_handles_null_payload():
    result = _format_hit({"payload": None})

    assert "unknown" in result


def test_format_hit_omits_line_range_when_lines_missing():
    result = _format_hit(make_hit(start_line=None, end_line=None))

    assert "src/app.py" in result
    assert "src/app.py:" not in result


# ================================================================
# find_function - Qdrant scroll mocked
# ================================================================


def make_point(**payload):
    base = {
        "name": "Session.get",
        "type": "method",
        "file_path": "src/sessions.py",
        "start_line": 5,
        "end_line": 9,
    }
    base.update(payload)
    return type("Point", (), {"payload": base})()


def test_find_function_formats_exact_matches(mocker):
    mocker.patch.object(
        tools.qdrant_client, "scroll", return_value=([make_point()], None)
    )

    result = find_function.func("get")

    assert "method `Session.get`" in result
    assert "src/sessions.py:5-9" in result


def test_find_function_queries_with_the_given_name(mocker):
    scroll = mocker.patch.object(
        tools.qdrant_client, "scroll", return_value=([make_point()], None)
    )

    find_function.func("retry_request")

    kwargs = scroll.call_args.kwargs
    assert kwargs["collection_name"] == tools.DEFAULT_COLLECTION
    assert kwargs["limit"] == 20
    assert kwargs["with_payload"] is True


def test_find_function_falls_back_to_fuzzy_when_exact_empty(mocker):
    scroll = mocker.patch.object(
        tools.qdrant_client,
        "scroll",
        side_effect=[([], None), ([make_point(name="fuzzy_hit")], None)],
    )

    result = find_function.func("fuzzy")

    assert scroll.call_count == 2
    assert "fuzzy_hit" in result


def test_find_function_no_matches_message(mocker):
    mocker.patch.object(
        tools.qdrant_client, "scroll", side_effect=[([], None), ([], None)]
    )

    result = find_function.func("nonexistent")

    assert result == "No function or class named 'nonexistent' found."


def test_find_function_lookup_error_is_caught(mocker):
    mocker.patch.object(
        tools.qdrant_client, "scroll", side_effect=ConnectionError("down")
    )

    result = find_function.func("x")

    assert "Error: lookup failed" in result
