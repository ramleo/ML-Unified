"""Shared helpers for the test-case assertion suites."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


UNIFIED = Path(__file__).resolve().parents[2]
PORTFOLIO = UNIFIED.parent / "ml-portfolio"
API = UNIFIED / "services" / "ml-api"


# --------------------------------------------------------------------------- helpers
def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def tracked_files(root: Path, *patterns: str) -> list[Path]:
    """git-tracked files matching the patterns — avoids .venv/node_modules noise."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", *patterns],
                         capture_output=True, text=True).stdout
    return [root / line for line in out.splitlines() if (root / line).is_file()]


def grep_tracked(root: Path, pattern: str, *globs: str) -> list[str]:
    """Every 'path:line' in tracked files matching a regex."""
    rx = re.compile(pattern)
    hits = []
    for f in tracked_files(root, *globs):
        try:
            for n, line in enumerate(read(f).splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(root)}:{n}")
        except (OSError, UnicodeDecodeError):
            continue
    return hits


def requirements() -> str:
    return read(API / "requirements.txt")
