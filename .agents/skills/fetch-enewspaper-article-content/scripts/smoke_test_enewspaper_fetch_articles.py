#!/usr/bin/env python3
"""Tiny smoke test for enewspaper_fetch_article-content.py.

This only checks that --dry-run executes successfully.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enewspaper_fetch_article-content.py"


def main() -> int:
    cmd = [
        sys.executable,
        "-u",
        str(SCRIPT),
        "--dry-run",
        "--article-url",
        "https://www.e-newspaperarchives.ch/?a=d&d=TEST0001",
    ]
    completed = subprocess.run(cmd, cwd=ROOT.parents[2], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

