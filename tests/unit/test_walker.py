"""Unit tests for the filesystem walker. Uses tmp_path only, no real repos."""

from pathlib import Path

import pytest

from lumora.ingestion.walker import (
    DEFAULT_SKIP_DIRS,
    DEFAULT_SKIP_EXT,
    walk_files,
)


def build_tree(root: Path, files):
    """Create each relative path under root with trivial content."""
    for rel in files:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")


def walk_names(root: Path):
    """Walk and return bare filenames for order-independent comparison."""
    return {p.name for p in walk_files(str(root))}


# --- normal files ---------------------------------------------------------------


def test_yields_normal_python_files(tmp_path):
    build_tree(tmp_path, ["main.py", "utils.py"])

    assert walk_names(tmp_path) == {"main.py", "utils.py"}


def test_yields_files_from_nested_directories(tmp_path):
    build_tree(tmp_path, ["pkg/sub/deep.py", "top.py"])

    assert walk_names(tmp_path) == {"deep.py", "top.py"}


def test_yields_non_python_source_files(tmp_path):
    """The walker is language-agnostic; filtering by language happens later."""
    build_tree(tmp_path, ["README.md", "app.js", "config.yaml"])

    assert walk_names(tmp_path) == {"README.md", "app.js", "config.yaml"}


def test_returns_path_objects(tmp_path):
    build_tree(tmp_path, ["main.py"])

    results = list(walk_files(str(tmp_path)))
    assert len(results) == 1
    assert isinstance(results[0], Path)
    assert results[0].is_absolute()


def test_is_a_lazy_generator(tmp_path):
    """Yielding lazily is the point of the function; assert it is not a list."""
    build_tree(tmp_path, ["main.py"])

    walker = walk_files(str(tmp_path))
    assert next(walker).name == "main.py"


# --- skipped directories --------------------------------------------------------


@pytest.mark.parametrize("junk_dir", sorted(DEFAULT_SKIP_DIRS))
def test_every_default_skip_dir_is_pruned(tmp_path, junk_dir):
    build_tree(tmp_path, [f"{junk_dir}/hidden.py", "keep.py"])

    assert walk_names(tmp_path) == {"keep.py"}


def test_nested_junk_dir_is_pruned(tmp_path):
    build_tree(tmp_path, ["pkg/node_modules/dep/index.js", "pkg/real.py"])

    assert walk_names(tmp_path) == {"real.py"}


def test_deeply_nested_content_under_junk_dir_is_pruned(tmp_path):
    build_tree(tmp_path, [".git/objects/ab/cdef.py", "src/app.py"])

    assert walk_names(tmp_path) == {"app.py"}


def test_directory_named_like_a_junk_dir_prefix_is_kept(tmp_path):
    """Pruning matches whole names, so `builder` must survive despite `build`."""
    build_tree(tmp_path, ["builder/tool.py", "build/artifact.py"])

    assert walk_names(tmp_path) == {"tool.py"}


# --- skipped extensions ---------------------------------------------------------


@pytest.mark.parametrize("ext", sorted(DEFAULT_SKIP_EXT))
def test_every_default_skip_extension_is_ignored(tmp_path, ext):
    build_tree(tmp_path, [f"asset{ext}", "keep.py"])

    assert walk_names(tmp_path) == {"keep.py"}


def test_skip_extension_match_is_case_insensitive(tmp_path):
    build_tree(tmp_path, ["IMAGE.PNG", "keep.py"])

    assert walk_names(tmp_path) == {"keep.py"}


def test_extensionless_file_is_yielded(tmp_path):
    build_tree(tmp_path, ["Makefile", "keep.py"])

    assert walk_names(tmp_path) == {"Makefile", "keep.py"}


# --- size limit -----------------------------------------------------------------


def test_files_over_size_limit_are_skipped(tmp_path):
    (tmp_path / "big.py").write_bytes(b"0" * 2048)
    (tmp_path / "small.py").write_bytes(b"0" * 10)

    results = {p.name for p in walk_files(str(tmp_path), max_file_size_mb=0.001)}
    assert results == {"small.py"}


def test_default_size_limit_keeps_ordinary_files(tmp_path):
    build_tree(tmp_path, ["main.py"])

    assert walk_names(tmp_path) == {"main.py"}


# --- invalid roots --------------------------------------------------------------


def test_nonexistent_root_yields_nothing(tmp_path):
    assert list(walk_files(str(tmp_path / "nope"))) == []


def test_file_as_root_yields_nothing(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("x")

    assert list(walk_files(str(target))) == []


def test_empty_directory_yields_nothing(tmp_path):
    assert list(walk_files(str(tmp_path))) == []
