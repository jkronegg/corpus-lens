#!/usr/bin/env python3
"""Tests unitaires pour fetch_dodis_person_details.py."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPTS_DIR / "fetch_dodis_person_details.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_dodis_person_details", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FetchDodisPersonDetailsTests(unittest.TestCase):
    def test_find_person_exact(self):
        rows = [
            {
                "prénom": "Thierry",
                "nom": "Pun",
                "année de naissance": "1956",
                "année de décès": "",
                "URL": "https://dodis.ch/P80148",
            }
        ]
        found = mod.find_person(rows, "Thierry Pun")
        self.assertIsNotNone(found)
        self.assertEqual(found["nom"], "Pun")

    def test_find_person_tokenized(self):
        rows = [
            {"prénom": "Jean-Pascal", "nom": "Delamuraz", "URL": "https://dodis.ch/123"}
        ]
        found = mod.find_person(rows, "Delamuraz Jean")
        self.assertIsNotNone(found)
        self.assertEqual(found["prénom"], "Jean-Pascal")

    def test_find_person_missing(self):
        rows = [{"prénom": "Alice", "nom": "Durand", "URL": "https://dodis.ch/456"}]
        self.assertIsNone(mod.find_person(rows, "Thierry Pun"))

    def test_load_people_reads_utf8_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "persons.csv"
            csv_path.write_text(
                "prénom,nom,année de naissance,année de décès,URL\nThierry,Pun,1956,,https://dodis.ch/P80148\n",
                encoding="utf-8",
            )
            rows = mod.load_people(csv_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["prénom"], "Thierry")

    def test_build_markdown_contains_required_fields(self):
        person = {
            "prénom": "Thierry",
            "nom": "Pun",
            "année de naissance": "1956",
            "année de décès": "",
            "URL": "https://dodis.ch/P80148",
        }
        md = mod.build_markdown(
            person=person,
            query="Thierry Pun",
            source_url="https://dodis.ch/P80148",
            page_title="Dodis Person",
            page_text="Contenu de test",
            persons_csv=Path(".agents/skills/fetch-dodis-person-details/assets/persons.csv"),
        )
        self.assertIn('transformation_by: "skill fetch-dodis-person-details"', md)
        self.assertIn("## Page 1", md)
        self.assertIn("## Contenu Dodis", md)
        self.assertIn("Contenu de test", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)

