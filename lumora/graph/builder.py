"""Dependency graph extraction.

Produces the node/edge structure the constellation view renders. Edges come
from two tree-sitter passes over each file: module-level imports, and call
expressions resolved against the symbol table built in the first pass.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from tree_sitter_language_pack import get_parser

logger = logging.getLogger(__name__)

PARSER = get_parser("python")

# Beyond this the force layout stops being readable and starts being a hairball;
# the API trims to the highest-degree nodes rather than returning everything.
DEFAULT_MAX_NODES = 100


def _text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _module_name(rel_path: Path) -> str:
    """Dotted module path for a repo-relative file, with __init__ collapsed to its package."""
    parts = list(rel_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _walk(root: Any) -> Iterable[Any]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _collect_imports(tree: Any, source: bytes, module: str) -> List[Tuple[str, str]]:
    """Return (imported_module, imported_symbol) pairs; symbol is "" for plain module imports."""
    imports: List[Tuple[str, str]] = []

    for node in _walk(tree.root_node):
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append((_text(child, source), ""))
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        imports.append((_text(name_node, source), ""))

        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node is None:
                continue
            base = _text(module_node, source)

            # A leading dot is a relative import; resolve it against this
            # file's own package so the edge points at a real module.
            if base.startswith("."):
                level = len(base) - len(base.lstrip("."))
                pkg_parts = module.split(".")[: -level] if module else []
                tail = base.lstrip(".")
                base = ".".join([p for p in pkg_parts if p] + ([tail] if tail else []))

            named = [
                _text(c, source)
                for c in node.children
                if c.type == "dotted_name" and c != module_node
            ]
            for c in node.children:
                if c.type == "aliased_import":
                    n = c.child_by_field_name("name")
                    if n is not None:
                        named.append(_text(n, source))

            if named:
                imports.extend((base, name) for name in named)
            else:
                imports.append((base, ""))

    return imports


def _enclosing_symbol(node: Any, source: bytes) -> Optional[str]:
    """Qualified name of the function/class that lexically contains `node`."""
    parts: List[str] = []
    current = node.parent
    while current is not None:
        if current.type in ("function_definition", "class_definition"):
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                parts.append(_text(name_node, source))
        current = current.parent
    if not parts:
        return None
    return ".".join(reversed(parts))


def _collect_definitions(
    tree: Any, source: bytes, module: str, rel_path: str
) -> List[Dict[str, Any]]:
    defs: List[Dict[str, Any]] = []
    for node in _walk(tree.root_node):
        if node.type not in ("function_definition", "class_definition"):
            continue
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        short = _text(name_node, source)
        parent = _enclosing_symbol(node, source)
        qualified = f"{parent}.{short}" if parent else short
        kind = (
            "class"
            if node.type == "class_definition"
            else ("method" if parent else "function")
        )
        defs.append(
            {
                "id": f"{module}:{qualified}" if module else f"{rel_path}:{qualified}",
                "label": short,
                "qualified": qualified,
                "file": rel_path,
                "module": module,
                "type": kind,
                "line": node.start_point[0] + 1,
            }
        )
    return defs


def _collect_calls(tree: Any, source: bytes) -> List[Tuple[Optional[str], str]]:
    """Return (calling_symbol, called_name) pairs. Called name is the last attribute segment."""
    calls: List[Tuple[Optional[str], str]] = []
    for node in _walk(tree.root_node):
        if node.type != "call":
            continue
        fn = node.child_by_field_name("function")
        if fn is None:
            continue
        if fn.type == "identifier":
            called = _text(fn, source)
        elif fn.type == "attribute":
            attr = fn.child_by_field_name("attribute")
            if attr is None:
                continue
            called = _text(attr, source)
        else:
            continue
        calls.append((_enclosing_symbol(node, source), called))
    return calls


def build_graph(
    repo_root: str, max_nodes: int = DEFAULT_MAX_NODES
) -> Dict[str, Any]:
    """Parse every Python file under `repo_root` into a node/edge dependency graph."""
    from lumora.ingestion.walker import walk_files

    root = Path(repo_root).resolve()

    file_nodes: Dict[str, Dict[str, Any]] = {}
    symbol_nodes: Dict[str, Dict[str, Any]] = {}
    # Short name -> owning node ids, used to resolve call targets.
    by_short_name: Dict[str, Set[str]] = defaultdict(set)
    module_to_file: Dict[str, str] = {}
    per_file: List[Tuple[str, str, Any, bytes]] = []

    for path in walk_files(str(root)):
        if path.suffix != ".py":
            continue
        try:
            source = path.read_bytes()
            tree = PARSER.parse(source)
        except (OSError, ValueError):
            logger.warning("Skipping unreadable file: %s", path)
            continue

        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            continue
        rel_path = rel.as_posix()
        module = _module_name(rel)

        file_id = f"file:{rel_path}"
        file_nodes[file_id] = {
            "id": file_id,
            "label": rel.name,
            "file": rel_path,
            "type": "file",
        }
        if module:
            module_to_file[module] = file_id

        for definition in _collect_definitions(tree, source, module, rel_path):
            symbol_nodes[definition["id"]] = definition
            by_short_name[definition["label"]].add(definition["id"])

        per_file.append((rel_path, module, tree, source))

    nodes: Dict[str, Dict[str, Any]] = {**file_nodes, **symbol_nodes}
    edges: Set[Tuple[str, str, str]] = set()

    for rel_path, module, tree, source in per_file:
        file_id = f"file:{rel_path}"

        for imported_module, imported_symbol in _collect_imports(tree, source, module):
            target_file = module_to_file.get(imported_module)
            if target_file is None:
                continue  # third-party or stdlib — outside this repo's graph
            if target_file != file_id:
                edges.add((file_id, target_file, "import"))

            if imported_symbol:
                target_id = f"{imported_module}:{imported_symbol}"
                if target_id in symbol_nodes:
                    edges.add((file_id, target_id, "import"))

        for caller, called in _collect_calls(tree, source):
            targets = by_short_name.get(called)
            if not targets:
                continue
            # An ambiguous short name would add edges the code does not have.
            if len(targets) != 1:
                continue
            target_id = next(iter(targets))

            source_id = (
                f"{module}:{caller}" if module and caller else f"{rel_path}:{caller}"
            )
            if caller is None or source_id not in symbol_nodes:
                source_id = file_id
            if source_id != target_id:
                edges.add((source_id, target_id, "call"))

    return _trim(nodes, edges, max_nodes)


def _trim(
    nodes: Dict[str, Dict[str, Any]],
    edges: Set[Tuple[str, str, str]],
    max_nodes: int,
) -> Dict[str, Any]:
    """Keep the highest-degree nodes so the layout stays legible on large repos."""
    degree: Dict[str, int] = defaultdict(int)
    for source, target, _ in edges:
        degree[source] += 1
        degree[target] += 1

    total = len(nodes)
    if total > max_nodes:
        ranked = sorted(nodes, key=lambda n: (-degree[n], n))
        kept = set(ranked[:max_nodes])
    else:
        kept = set(nodes)

    out_nodes = [
        {**nodes[n], "degree": degree[n]} for n in sorted(kept, key=lambda n: (-degree[n], n))
    ]
    out_edges = [
        {"source": s, "target": t, "kind": k}
        for s, t, k in sorted(edges)
        if s in kept and t in kept
    ]

    return {
        "nodes": out_nodes,
        "edges": out_edges,
        "truncated": total > max_nodes,
        "total_nodes": total,
    }
