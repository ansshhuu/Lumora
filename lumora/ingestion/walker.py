from pathlib import Path
import os
from typing import Set, Iterator

# Default skips - focused and practical
DEFAULT_SKIP_DIRS: Set[str] = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", ".nuxt", "target"
}

DEFAULT_SKIP_EXT: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".zip", ".tar", ".gz", ".woff", ".ttf"
}


def walk_files(root: str, max_file_size_mb:int=10)->Iterator[Path]:#ek ek karke files return krta hai memory save krne ko 
    root_path=Path(root).resolve()
    skip_dirs = DEFAULT_SKIP_DIRS
    skip_ext = DEFAULT_SKIP_EXT

    for dirpath,dirnames,filenames in os.walk(root_path,followlinks=False):
        current_dir=Path(dirpath)

        # Early prune: stop walking into junk directories
        dirnames[:]=[d for d in dirnames if d not in skip_dirs]

        if any(part in skip_dirs for part in current_dir.parts):
            continue
        for filename in filenames:
            file_path=current_dir/filename

            # Skip unwanted extensions
            if file_path.suffix.lower() in skip_ext:
                continue
            # Skip large files
            try:
                if file_path.stat().st_size > max_file_size_mb * 1024 * 1024:
                    continue
            except OSError:
                continue

            yield file_path #Jo valid file mili hai, uska path return karo aur baad me baaki files dhoondhna continue rakho.


