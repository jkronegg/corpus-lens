#!/usr/bin/env python3
"""Tests unitaires pour fetch_dodis_document_content.py."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPTS_DIR / "fetch_dodis_document_content.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_dodis_document_content", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FetchDodisDocumentContentTests(unittest.TestCase):
    def test_normalize_document_id(self):
        self.assertEqual(mod.normalize_document_id(" 43445 "), "43445")

    def test_normalize_document_id_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            mod.normalize_document_id("43A45")

    def test_build_document_url(self):
        self.assertEqual(mod.build_document_url("43445"), "https://dodis.ch/43445?lang=fr")

    def test_guess_output_name(self):
        self.assertEqual(mod.guess_output_name("43445"), "dodis_document_43445.md")

    def test_build_markdown_contains_required_fields(self):
        md = mod.build_markdown(
            document_id="43445",
            source_url="https://dodis.ch/43445?lang=fr",
            page_title="Document Dodis",
            page_text="Contenu de test",
            sections=[],
            root_blocks=[],
            downloaded_images=[],
        )
        self.assertIn('transformation_by: "skill fetch-dodis-document-content"', md)
        self.assertIn("## Page 1", md)
        self.assertIn("## Contenu Dodis structuré", md)
        self.assertIn("Contenu de test", md)
        self.assertIn("Identifiant Dodis: 43445", md)

    def test_build_markdown_uses_fallback_title(self):
        md = mod.build_markdown(
            document_id="43445",
            source_url="https://dodis.ch/43445?lang=fr",
            page_title="",
            page_text="Texte",
            sections=[],
            root_blocks=[],
            downloaded_images=[],
        )
        self.assertIn("Document Dodis 43445", md)

    def test_slugify_keeps_numeric_identifier(self):
        self.assertEqual(mod.slugify("43445"), "43445")

    def test_load_markdown_table_basic(self):
        lines = mod._build_markdown_table(
            ["Date", "Sujet"],
            [{"cells": ["01.01.2024", "Test"], "url": ""}],
        )
        self.assertEqual(lines[0], "| Date | Sujet |")
        self.assertIn("Test", "\n".join(lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)

