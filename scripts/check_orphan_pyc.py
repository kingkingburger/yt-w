"""Remove orphan .pyc files whose source .py no longer exists.

Stale bytecode survives module renames/deletes and can mask real import errors
or tools like vulture; this hook deletes orphans on every commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXCLUDE_DIRS = {".venv", ".git", "node_modules"}


def find_orphans(root: Path) -> list[Path]:
    orphans: list[Path] = []
    for pycache in root.rglob("__pycache__"):
        if any(part in EXCLUDE_DIRS for part in pycache.parts):
            continue
        source_dir = pycache.parent
        for pyc in pycache.glob("*.pyc"):
            stem = pyc.name.split(".cpython", 1)[0]
            if not (source_dir / f"{stem}.py").exists():
                orphans.append(pyc)
    return orphans


def main() -> int:
    root = Path.cwd()
    orphans = find_orphans(root)
    for pyc in orphans:
        try:
            pyc.unlink()
            print(f"removed orphan: {pyc.relative_to(root)}")
        except OSError as error:
            print(f"failed to remove {pyc}: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
