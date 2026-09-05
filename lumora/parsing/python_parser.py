import os
from pathlib import Path

from typing import List,Dict,Any,Optional

from tree_sitter_language_pack import get_parser
PARSER = get_parser("python")

def extract_docstring(node:Any,source_bytes:bytes)-> Optional[str]:
    body_node=node.child_by_field_name("body")
    if not body_node or not body_node.children:
        return None
    first_child=body_node.children[0]

    # Depending on grammar version the docstring is either a bare `string` node
    # in the block or wrapped in an `expression_statement`.
    string_node=None
    if first_child.type == "string":
        string_node=first_child
    elif first_child.type == "expression_statement" and first_child.children:
        candidate=first_child.children[0]
        if candidate.type == "string":
            string_node=candidate

    if string_node is not None:
        doc = source_bytes[string_node.start_byte : string_node.end_byte].decode("utf-8", errors="ignore")
        return doc.strip(" '\"")
    return None

def extract_functions_and_classes(file_path: str, repo_root: str = "") -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "rb") as f:
            source_bytes = f.read()
    except IOError:
        return []
    try:
        tree = PARSER.parse(source_bytes)
    except Exception:
        return []

    results = []
    try:
        rel_path = str(Path(file_path).resolve().relative_to(Path(repo_root).resolve())) if repo_root else file_path
    except ValueError:
        rel_path = file_path
    stack = [(tree.root_node, "")]
    while stack:
        node, parent_prefix = stack.pop()
        current_type = node.type
        is_target = current_type in ("function_definition", "class_definition")
        next_parent_prefix = parent_prefix

        if is_target:
            name_node = node.child_by_field_name("name")
            name = (
                source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                if name_node else "unknown"
            )
            full_name = f"{parent_prefix}.{name}" if parent_prefix else name
            docstring = extract_docstring(node, source_bytes)
            node_kind = (
                "method" if (parent_prefix and current_type == "function_definition")
                else current_type.replace("_definition", "")
            )
            results.append({
                "type": node_kind,
                "name": full_name,
                "short_name": name,
                "file_path": rel_path,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "docstring": docstring,
                "code": source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore"),
            })
            if current_type == "class_definition":
                next_parent_prefix = full_name

        for child in reversed(node.children):
            stack.append((child, next_parent_prefix))

    return results




