#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).resolve().parent / "detect_markdown_language.py"

    sample = """---
titre: "Doc test"
---

## Page 1

Der Soldat ist bereit und die Truppe ist mobilisee.
Le soldat est pret et la troupe est mobilisee.
"""

    with tempfile.TemporaryDirectory() as tmp_dir_raw:
        tmp_dir = Path(tmp_dir_raw)
        input_path = tmp_dir / "input.md"
        input_path.write_text(sample, encoding="utf-8")

        dry_run = subprocess.run(
            ["python", "-u", str(script_path), "--input", str(input_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        assert ":" in dry_run.stdout.strip(), "distribution output is missing"

        subprocess.run(
            ["python", "-u", str(script_path), "--input", str(input_path), "--write"],
            check=True,
        )

        updated = input_path.read_text(encoding="utf-8")
        assert "language_distribution:" in updated, "front matter field not written"

    print("ok: smoke test detect-markdown-language")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

