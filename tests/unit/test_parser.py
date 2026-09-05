"""Unit tests for the tree-sitter Python parser. No network, no I/O beyond fixtures."""

from pathlib import Path


from lumora.parsing.python_parser import (
    extract_docstring,
    extract_functions_and_classes,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def by_name(results):
    """Index parser output by qualified name for readable assertions."""
    return {r["name"]: r for r in results}


# --- simple function extraction -------------------------------------------------


def test_extracts_all_top_level_functions():
    results = extract_functions_and_classes(str(FIXTURES / "simple_functions.py"))
    names = by_name(results)

    assert {"greet", "add", "outer"} <= set(names)
    assert all(r["type"] == "function" for r in results)


def test_function_line_numbers_are_one_indexed_and_span_body():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "simple_functions.py")))

    greet = results["greet"]
    assert greet["start_line"] == 4
    assert greet["end_line"] == 6

    add = results["add"]
    assert add["start_line"] == 9
    assert add["end_line"] == 10


def test_function_code_slice_matches_source():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "simple_functions.py")))

    code = results["add"]["code"]
    assert code.startswith("def add(a, b):")
    assert "return a + b" in code


def test_nested_function_is_extracted():
    """A def inside a def is reported, but is not treated as a method."""
    results = by_name(extract_functions_and_classes(str(FIXTURES / "simple_functions.py")))

    assert "inner" in results
    assert results["inner"]["type"] == "function"


# --- class and method extraction ------------------------------------------------


def test_class_is_extracted_with_class_type():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "classes_and_methods.py")))

    assert results["Calculator"]["type"] == "class"
    assert results["Calculator"]["short_name"] == "Calculator"


def test_methods_get_qualified_names():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "classes_and_methods.py")))

    assert "Calculator.add" in results
    assert "Calculator.subtract" in results

    add = results["Calculator.add"]
    assert add["type"] == "method"
    assert add["short_name"] == "add"


def test_nested_class_and_method_names_are_fully_qualified():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "classes_and_methods.py")))

    assert "Outer.Inner" in results
    assert results["Outer.Inner"]["type"] == "class"

    assert "Outer.Inner.deep_method" in results
    assert results["Outer.Inner.deep_method"]["type"] == "method"


def test_module_level_function_is_not_prefixed_by_a_class():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "classes_and_methods.py")))

    assert "standalone" in results
    assert results["standalone"]["type"] == "function"


# --- docstrings -----------------------------------------------------------------


def test_docstring_present_is_extracted_and_stripped_of_quotes():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "simple_functions.py")))

    assert results["greet"]["docstring"] == "Return a greeting for the given name."


def test_class_and_method_docstrings_are_extracted():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "classes_and_methods.py")))

    assert results["Calculator"]["docstring"] == "A small calculator."
    assert results["Calculator.add"]["docstring"] == "Add two numbers."
    assert results["Outer.Inner"]["docstring"] == "A nested class."


def test_docstring_absent_is_none():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "simple_functions.py")))

    assert results["add"]["docstring"] is None


def test_leading_string_assignment_is_not_a_docstring():
    """`x = "..."` as the first statement must not be mistaken for a docstring."""
    results = by_name(extract_functions_and_classes(str(FIXTURES / "no_docstrings.py")))

    assert results["plain"]["docstring"] is None
    assert results["Bare"]["docstring"] is None
    assert results["Bare.method"]["docstring"] is None


def test_extract_docstring_returns_none_for_node_without_body():
    """Guard clause: a node with no body field yields None rather than raising."""

    class _NoBody:
        def child_by_field_name(self, _name):
            return None

    assert extract_docstring(_NoBody(), b"") is None


# --- malformed and edge-case inputs ---------------------------------------------


def test_malformed_syntax_does_not_crash():
    """tree-sitter is error-tolerant: it recovers what it can instead of raising."""
    results = extract_functions_and_classes(str(FIXTURES / "broken_syntax.py.txt"))

    assert isinstance(results, list)
    assert all("name" in r and "start_line" in r for r in results)


def test_malformed_syntax_still_recovers_the_valid_function():
    results = by_name(extract_functions_and_classes(str(FIXTURES / "broken_syntax.py.txt")))

    assert "valid_before" in results


def test_empty_file_returns_empty_list():
    assert extract_functions_and_classes(str(FIXTURES / "empty.py")) == []


def test_missing_file_returns_empty_list():
    assert extract_functions_and_classes(str(FIXTURES / "does_not_exist.py")) == []


def test_directory_path_returns_empty_list_instead_of_raising():
    """A directory exists but cannot be read as a file; must not propagate IOError."""
    assert extract_functions_and_classes(str(FIXTURES)) == []


# --- repo_root relative paths ---------------------------------------------------


def test_file_path_is_relative_to_repo_root_when_given():
    results = extract_functions_and_classes(
        str(FIXTURES / "simple_functions.py"), repo_root=str(FIXTURES)
    )

    assert results
    assert results[0]["file_path"] == "simple_functions.py"


def test_file_path_is_absolute_when_no_repo_root():
    target = str(FIXTURES / "simple_functions.py")
    results = extract_functions_and_classes(target)

    assert results[0]["file_path"] == target


def test_repo_root_outside_file_tree_falls_back_to_full_path(tmp_path):
    """An unrelated repo_root raises ValueError internally and falls back."""
    target = str(FIXTURES / "simple_functions.py")
    results = extract_functions_and_classes(target, repo_root=str(tmp_path))

    assert results[0]["file_path"] == target
