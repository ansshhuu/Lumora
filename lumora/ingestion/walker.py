import os
from pathlib import Path
from typing import Set, Iterator

DEFAULT_SKIP_DIRS: Set[str] = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", ".nuxt", "target", ".pytest_cache", ".coverage"
}

DEFAULT_SKIP_EXT: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".zip", ".tar", ".gz", ".woff", ".ttf", ".pdf", ".mp4"
}

def walk_files(root: str, max_file_size_mb: int = 10) -> Iterator[Path]:
    """
    Efficiently yields valid file paths from a root directory while pruning skipped folders
    and ignoring binary/large assets. Yields generator elements to minimize RAM footprint.
    """
    root_path = Path(root).resolve()
    
    if not root_path.exists() or not root_path.is_dir():
        return

    max_bytes = max_file_size_mb * 1024 * 1024

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
        current_dir = Path(dirpath)

        # In-place directory pruning (modifying dirnames array stops os.walk from recursing inside them)
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]

        # Double-check path parts safety
        if any(part in DEFAULT_SKIP_DIRS for part in current_dir.parts):
            continue

        for filename in filenames:
            file_path = current_dir / filename

            # Skip junk extensions
            if file_path.suffix.lower() in DEFAULT_SKIP_EXT:
                continue

            # Skip large files without breaking execution on broken symlinks or system locking
            try:
                if file_path.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue

            yield file_path