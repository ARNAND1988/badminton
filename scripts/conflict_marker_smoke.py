#!/usr/bin/env python3
"""Fail when unresolved Git merge markers remain in tracked text files."""
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKERS = ("<" * 7, "=" * 7, ">" * 7)


def main() -> int:
    result = subprocess.run(
        ["git", "grep", "-n", "-I", "-E", rf"^({'|'.join(MARKERS)})( |$)"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode == 1:
        print("No unresolved merge conflict markers found.")
        return 0
    if result.returncode > 1:
        print(result.stderr, end="")
        return result.returncode

    print("Unresolved merge conflict markers found:")
    print(result.stdout, end="")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
