#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SKILL_NAME = "extract-pdf-to-md-all-sources"


@dataclass
class FileResult:
    pdf_path: str
    md_path: str
    status: str
    pages: int | None = None
    error: str | None = None


def _load_unit_extractor(repo_root: Path):
    script_path = repo_root / ".agents" / "skills" / "extract-pdf-to-md" / "scripts" / "pdf_to_md_extractor.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Unit extractor not found: {script_path}")

    module_name = "extract_pdf_to_md_unit"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "extract_pdf_to_md"):
        raise AttributeError("Function `extract_pdf_to_md` not found in unit extractor")

    return module.extract_pdf_to_md


def _load_db_module(repo_root: Path):
    script_path = repo_root / ".agents" / "skills" / "manage-named-entities-db" / "scripts" / "db.py"
    if not script_path.exists():
        return None

    module_name = "extract_pdf_to_md_all_sources_db"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _default_sources_root() -> Path:
    return Path(__file__).resolve().parents[4] / "sources"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch extract all PDFs under sources/**/*.pdf to Markdown")
    parser.add_argument(
        "--sources-root",
        type=Path,
        default=_default_sources_root(),
        help="Root directory to scan for PDFs (default: <repo>/sources)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate Markdown even if .md already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be processed",
    )
    return parser.parse_args()


def _print_progress(current: int, total: int, width: int = 30) -> None:
    if total <= 0:
        return
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\rConversion PDF vers Markdown: [{bar}] {current}/{total}", end="", file=sys.stderr, flush=True)
    if current == total:
        print(file=sys.stderr)


def _collect_pdf_candidates_from_db(repo_root: Path, sources_root: Path) -> tuple[list[Path], str]:
    db_module = _load_db_module(repo_root)
    if db_module is None:
        return [], "db_unavailable"

    get_connection = getattr(db_module, "get_connection", None)
    list_sources_for_ocr = getattr(db_module, "list_sources_for_ocr", None)
    if not callable(get_connection) or not callable(list_sources_for_ocr):
        return [], "db_api_unavailable"

    get_connection_fn = get_connection
    list_sources_for_ocr_fn = list_sources_for_ocr

    con = None
    try:
        con = get_connection_fn()
        rows = list_sources_for_ocr_fn(con, statuses=("P", "F", "T"))
    finally:
        if con is not None:
            con.close()

    pdf_files: list[Path] = []
    for row in rows:
        raw_path = str(row.get("document_path") or row.get("origine") or "").strip()
        if not raw_path:
            continue
        candidate = (repo_root / raw_path).resolve()
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            candidate.relative_to(sources_root)
        except ValueError:
            continue
        pdf_files.append(candidate)

    unique_sorted = sorted({path.resolve() for path in pdf_files})
    return unique_sorted, "db"


def main() -> int:
    args = parse_args()

    sources_root = args.sources_root.resolve()
    if not sources_root.exists():
        raise FileNotFoundError(f"sources root not found: {sources_root}")

    repo_root = Path(__file__).resolve().parents[4]
    extract_pdf_to_md = _load_unit_extractor(repo_root)

    pdf_files, selection_mode = _collect_pdf_candidates_from_db(repo_root, sources_root)
    if not pdf_files:
        pdf_files = sorted(path for path in sources_root.rglob("*.pdf") if path.is_file())
        selection_mode = "filesystem"
    pdf_total = len(pdf_files)
    results: list[FileResult] = []

    if pdf_total > 0:
        _print_progress(0, pdf_total)

    for index, pdf_path in enumerate(pdf_files, start=1):
        md_path = pdf_path.with_suffix(".md")
        should_skip_existing_md = selection_mode == "filesystem"

        if should_skip_existing_md and md_path.exists() and not args.overwrite:
            results.append(FileResult(pdf_path=str(pdf_path), md_path=str(md_path), status="skipped_exists"))
            _print_progress(index, pdf_total)
            continue

        if args.dry_run:
            results.append(FileResult(pdf_path=str(pdf_path), md_path=str(md_path), status="planned"))
            _print_progress(index, pdf_total)
            continue

        try:
            pages = int(extract_pdf_to_md(pdf_path, md_path))
            results.append(FileResult(pdf_path=str(pdf_path), md_path=str(md_path), status="extracted", pages=pages))
        except Exception as exc:
            results.append(FileResult(pdf_path=str(pdf_path), md_path=str(md_path), status="error", error=str(exc)))
        _print_progress(index, pdf_total)

    summary = {
        "transformation_by": "skill " + SKILL_NAME,
        "sources_root": str(sources_root),
        "overwrite": bool(args.overwrite),
        "dry_run": bool(args.dry_run),
        "selection_mode": selection_mode,
        "counts": {
            "pdf_total": len(pdf_files),
            "planned": sum(1 for r in results if r.status == "planned"),
            "extracted": sum(1 for r in results if r.status == "extracted"),
            "skipped_exists": sum(1 for r in results if r.status == "skipped_exists"),
            "errors": sum(1 for r in results if r.status == "error"),
        },
        "results": [asdict(r) for r in results if r.status != "skipped_exists"],
    }

    counts = summary["counts"]
    only_skipped = (
        counts["pdf_total"] > 0
        and counts["skipped_exists"] == counts["pdf_total"]
        and counts["planned"] == 0
        and counts["extracted"] == 0
        and counts["errors"] == 0
    )
    if only_skipped:
        print("Aucun PDF à convertir")
        return 0

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if summary["counts"]["errors"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

