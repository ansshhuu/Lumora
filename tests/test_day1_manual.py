"""
Day 1 manual test — run with:
poetry run python tests/test_day1_manual.py
"""

from pathlib import Path

from lumora.ingestion.clone import clone_repo
from lumora.ingestion.walker import walk_files
from lumora.parsing.python_parser import (
    extract_functions_and_classes,
    PARSER,
)

REPO_URL = "https://github.com/tiangolo/fastapi"
DEST = "test_repos/fastapi"

# Clone if needed
if not Path(DEST).exists():
    repo_path = Path(clone_repo(REPO_URL, DEST))
else:
    repo_path = Path(DEST)

# Optional sanity check on one known file
sample_file = repo_path / "fastapi" / "applications.py"

if sample_file.exists():
    r = extract_functions_and_classes(str(sample_file))
    print(len(r))
    print(r[0] if r else "EMPTY")

    with open(sample_file, "rb") as f:
        src = f.read()

    tree = PARSER.parse(src)
    print(tree.root_node.type, len(tree.root_node.children))
else:
    print(f"Sample file not found: {sample_file}")

total_files = 0
total_items = 0
failed_files = []

for file_path in walk_files(str(repo_path)):
    if file_path.suffix != ".py":
        continue

    total_files += 1

    try:
        items = extract_functions_and_classes(
            str(file_path),
            repo_root=str(repo_path)
        )
    except Exception as e:
        failed_files.append((str(file_path), str(e)))
        continue

    total_items += len(items)

    for fn in items:
        doc_preview = (
            fn["docstring"][:40] + "..."
            if fn["docstring"]
            else "-"
        )

        print(
            f"{fn['type']:8} "
            f"{fn['name']:35} "
            f"{fn['file_path']}:{fn['start_line']}-{fn['end_line']} "
            f"doc: {doc_preview}"
        )

print("\n---")
print(f"Files scanned: {total_files}")
print(f"Functions/classes/methods found: {total_items}")
print(f"Failed files: {len(failed_files)}")

for f, err in failed_files:
    print(f"  {f}: {err}")