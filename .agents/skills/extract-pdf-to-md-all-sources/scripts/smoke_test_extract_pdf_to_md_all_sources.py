#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / ".agents" / "skills" / "extract-pdf-to-md-all-sources" / "scripts" / "extract_pdf_to_md_all_sources.py"

    sample_pdf = repo_root / "sources" / "swissvotes" / "votation_86" / "texte_soumis_au_vote.pdf"
    if not sample_pdf.exists():
        print(f"skip: sample PDF not found: {sample_pdf}")
        return 0

    with tempfile.TemporaryDirectory() as td:
        sources_root = Path(td) / "sources"
        sources_root.mkdir(parents=True, exist_ok=True)

        copied_pdf = sources_root / sample_pdf.name
        shutil.copy2(sample_pdf, copied_pdf)

        run = subprocess.run(
            [
                "python",
                "-u",
                str(script),
                "--sources-root",
                str(sources_root),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(run.stdout)
        assert payload["counts"]["pdf_total"] == 1, "expected one PDF"
        assert payload["counts"]["extracted"] == 1, "expected one extraction"

        out_md = copied_pdf.with_suffix(".md")
        assert out_md.exists(), "output markdown was not created"
        content = out_md.read_text(encoding="utf-8", errors="replace")
        assert content.startswith("---\n"), "front matter missing"
        assert "## Page " in content, "page sections missing"

    print("ok: smoke test extract-pdf-to-md-all-sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

