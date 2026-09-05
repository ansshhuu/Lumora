"""End-to-end ingestion: walk the fixture repo, parse every module, assert the
exact inventory of definitions.

The fixture repo lives at tests/fixtures/sample_repo/ and is checked into git as
ordinary files. Nothing here clones, embeds, or touches the network, so the
counts below are stable and were hand-verified against the fixture sources.
"""

from collections import Counter
from pathlib import Path

import pytest

from lumora.ingestion.walker import walk_files
from lumora.parsing.python_parser import extract_functions_and_classes

SAMPLE_REPO = Path(__file__).parent.parent / "fixtures" / "sample_repo"

# Hand-verified from the fixture sources: 5 module-level functions,
# 5 classes (one of them nested), 12 methods.
EXPECTED_FUNCTIONS = {"build_store", "main", "add", "divide", "mean"}
EXPECTED_CLASSES = {
    "Accumulator",
    "RecordError",
    "Store",
    "Store.Config",
    "AuditedStore",
}
EXPECTED_METHODS = {
    "Accumulator.__init__",
    "Accumulator.push",
    "Accumulator.reset",
    "Accumulator.magnitude",
    "Store.Config.defaults",
    "Store.__init__",
    "Store.put",
    "Store.get",
    "Store.require",
    "Store.keys",
    "AuditedStore.__init__",
    "AuditedStore.put",
}
EXPECTED_TOTAL = len(EXPECTED_FUNCTIONS) + len(EXPECTED_CLASSES) + len(EXPECTED_METHODS)


def ingest(root: Path):
    """The walk + parse half of the indexing pipeline, with no embedding step.

    Mirrors lumora.api.routes.index._run_indexing, which filters walk_files
    down to .py before parsing.
    """
    items = []
    for file_path in walk_files(str(root)):
        if file_path.suffix == ".py":
            items.extend(
                extract_functions_and_classes(str(file_path), repo_root=str(root))
            )
    return items


@pytest.fixture(scope="module")
def items():
    return ingest(SAMPLE_REPO)


@pytest.fixture(scope="module")
def by_name(items):
    return {item["name"]: item for item in items}


# --- the fixture repo itself ----------------------------------------------------


def test_fixture_repo_is_present():
    """Guards against a fixture that silently failed to check in."""
    assert SAMPLE_REPO.is_dir()
    assert (SAMPLE_REPO / "cli.py").is_file()
    assert (SAMPLE_REPO / "sample_pkg" / "store.py").is_file()


# --- walking --------------------------------------------------------------------


def test_walker_finds_every_source_file():
    found = {p.name for p in walk_files(str(SAMPLE_REPO))}

    assert {"cli.py", "math_utils.py", "store.py", "__init__.py"} <= found
    assert {"README.md", "notes.txt"} <= found, "non-Python files are still yielded"


def test_walker_skips_binary_extensions():
    found = {p.name for p in walk_files(str(SAMPLE_REPO))}

    assert "logo.png" not in found


def test_walker_yields_four_python_modules():
    py_files = [p for p in walk_files(str(SAMPLE_REPO)) if p.suffix == ".py"]

    assert len(py_files) == 4


# --- counts ---------------------------------------------------------------------


def test_total_definition_count_matches_hand_verified_inventory(items):
    assert len(items) == EXPECTED_TOTAL == 22


def test_counts_split_by_kind(items):
    counts = Counter(item["type"] for item in items)

    assert counts == {"function": 5, "class": 5, "method": 12}


def test_every_expected_name_is_extracted(by_name):
    assert set(by_name) == EXPECTED_FUNCTIONS | EXPECTED_CLASSES | EXPECTED_METHODS


def test_package_init_contributes_no_definitions():
    """__init__.py holds only __version__, so it must parse to an empty list."""
    results = extract_functions_and_classes(
        str(SAMPLE_REPO / "sample_pkg" / "__init__.py"), repo_root=str(SAMPLE_REPO)
    )

    assert results == []


# --- record shape ---------------------------------------------------------------


def test_every_record_has_the_full_field_set(items):
    expected_fields = {
        "type",
        "name",
        "short_name",
        "file_path",
        "start_line",
        "end_line",
        "docstring",
        "code",
    }

    for item in items:
        assert set(item) == expected_fields, item["name"]


def test_file_paths_are_relative_to_the_repo_root(items):
    for item in items:
        path = Path(item["file_path"])
        assert not path.is_absolute(), item["name"]
        assert (SAMPLE_REPO / path).is_file(), item["name"]


def test_line_spans_are_one_indexed_and_ordered(items):
    for item in items:
        assert item["start_line"] >= 1, item["name"]
        assert item["end_line"] >= item["start_line"], item["name"]


def test_code_snippet_round_trips_against_the_source(by_name):
    """The extracted code must be the exact source slice for those lines."""
    divide = by_name["divide"]
    source_lines = (SAMPLE_REPO / divide["file_path"]).read_text(
        encoding="utf-8"
    ).splitlines()
    span = source_lines[divide["start_line"] - 1 : divide["end_line"]]

    assert divide["code"].splitlines() == [line for line in span]


# --- nesting and docstrings -----------------------------------------------------


def test_methods_are_qualified_by_their_class(by_name):
    push = by_name["Accumulator.push"]

    assert push["type"] == "method"
    assert push["short_name"] == "push"


def test_nested_class_and_its_method_are_fully_qualified(by_name):
    assert by_name["Store.Config"]["type"] == "class"
    assert by_name["Store.Config.defaults"]["type"] == "method"
    assert by_name["Store.Config.defaults"]["short_name"] == "defaults"


def test_same_method_name_on_two_classes_stays_distinct(by_name):
    """Store.put and AuditedStore.put must not collide."""
    assert "super().put(key, value)" in by_name["AuditedStore.put"]["code"]
    assert "super().put" not in by_name["Store.put"]["code"]


def test_docstrings_are_extracted(by_name):
    assert by_name["add"]["docstring"] == "Return the sum of two numbers."
    assert by_name["Store"]["docstring"] == "Keeps records in a dictionary keyed by id."


def test_missing_docstring_is_none_not_empty_string(by_name):
    """mean() has only a comment, so docstring must be None."""
    assert by_name["mean"]["docstring"] is None
