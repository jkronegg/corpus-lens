from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "extract_pdf_to_md_all_sources.py"
)


def load_module():
    module_name = "extract_pdf_to_md_all_sources"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load script module: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_main(module, sources_root: Path, overwrite: bool):
    stdout = io.StringIO()
    stderr = io.StringIO()
    args = argparse.Namespace(sources_root=sources_root, overwrite=overwrite)

    with (
        patch.object(module, "parse_args", return_value=args, create=True),
        patch.object(module, "_collect_pdf_candidates_from_db", return_value=([], "db_unavailable"), create=True),
        redirect_stdout(stdout),
        redirect_stderr(stderr),
    ):
        exit_code = module.main()

    return exit_code, stdout.getvalue()


class TestExtractPdfToMdAllSources(unittest.TestCase):
    def test_two_pdfs_in_different_directories_are_processed(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            sources_root = Path(tmp_dir) / "sources"
            (sources_root / "a").mkdir(parents=True)
            (sources_root / "b" / "nested").mkdir(parents=True)
            pdf_a = sources_root / "a" / "doc-a.pdf"
            pdf_b = sources_root / "b" / "nested" / "doc-b.pdf"
            pdf_a.write_bytes(b"%PDF-1.4\n")
            pdf_b.write_bytes(b"%PDF-1.4\n")

            calls: list[tuple[Path, Path]] = []

            def fake_extract(pdf_path: Path, md_path: Path) -> int:
                calls.append((pdf_path, md_path))
                md_path.write_text(f"converted:{pdf_path.name}\n", encoding="utf-8")
                return 1

            with patch.object(module, "_load_unit_extractor", return_value=fake_extract, create=True):
                exit_code, stdout_text = run_main(module, sources_root=sources_root, overwrite=False)

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(calls), 2)
            self.assertTrue(pdf_a.with_suffix(".md").exists())
            self.assertTrue(pdf_b.with_suffix(".md").exists())

            summary = json.loads(stdout_text)
            self.assertEqual(summary["selection_mode"], "filesystem")
            self.assertEqual(summary["counts"]["pdf_total"], 2)
            self.assertEqual(summary["counts"]["extracted"], 2)
            self.assertEqual(summary["counts"]["skipped_exists"], 0)
            self.assertEqual(summary["counts"]["errors"], 0)

    def test_idempotence_second_run_does_not_reextract(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            sources_root = Path(tmp_dir) / "sources"
            (sources_root / "x").mkdir(parents=True)
            (sources_root / "y").mkdir(parents=True)
            pdf_x = sources_root / "x" / "doc-x.pdf"
            pdf_y = sources_root / "y" / "doc-y.pdf"
            pdf_x.write_bytes(b"%PDF-1.4\n")
            pdf_y.write_bytes(b"%PDF-1.4\n")

            call_counter = {"count": 0}

            def fake_extract(pdf_path: Path, md_path: Path) -> int:
                call_counter["count"] += 1
                md_path.write_text("converted\n", encoding="utf-8")
                return 2

            with patch.object(module, "_load_unit_extractor", return_value=fake_extract, create=True):
                first_exit, first_stdout = run_main(module, sources_root=sources_root, overwrite=False)
                second_exit, second_stdout = run_main(module, sources_root=sources_root, overwrite=False)

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            self.assertEqual(call_counter["count"], 2)

            first_summary = json.loads(first_stdout)
            self.assertEqual(first_summary["counts"]["extracted"], 2)
            self.assertEqual(first_summary["counts"]["skipped_exists"], 0)

            self.assertEqual(second_stdout.strip(), "Aucun PDF à convertir")

    def test_overwrite_forces_new_extraction(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            sources_root = Path(tmp_dir) / "sources"
            (sources_root / "d1").mkdir(parents=True)
            (sources_root / "d2").mkdir(parents=True)
            pdf_1 = sources_root / "d1" / "doc-1.pdf"
            pdf_2 = sources_root / "d2" / "doc-2.pdf"
            pdf_1.write_bytes(b"%PDF-1.4\n")
            pdf_2.write_bytes(b"%PDF-1.4\n")

            call_counter = {"count": 0}

            def fake_extract(pdf_path: Path, md_path: Path) -> int:
                call_counter["count"] += 1
                md_path.write_text(f"run:{call_counter['count']}\n", encoding="utf-8")
                return 3

            with patch.object(module, "_load_unit_extractor", return_value=fake_extract, create=True):
                first_exit, _ = run_main(module, sources_root=sources_root, overwrite=False)
                second_exit, second_stdout = run_main(module, sources_root=sources_root, overwrite=True)

            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 0)
            self.assertEqual(call_counter["count"], 4)

            second_summary = json.loads(second_stdout)
            self.assertEqual(second_summary["counts"]["pdf_total"], 2)
            self.assertEqual(second_summary["counts"]["extracted"], 2)
            self.assertEqual(second_summary["counts"]["skipped_exists"], 0)
            self.assertEqual(second_summary["counts"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()





