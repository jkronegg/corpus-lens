#!/usr/bin/env python3
"""Tests unitaires pour fetch_elitesuisse_person_details.py."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "fetch_elitesuisse_person_details.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_elitesuisse_person_details", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module: {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FetchEliteSuisseUnitTests(unittest.TestCase):
    def test_normalize_handles_accents_and_spaces(self):
        self.assertEqual(mod._normalize("  ÉLITES   suisses  "), "elites suisses")

    def test_extract_person_id(self):
        url = "https://elitessuisses.unil.ch/personne.php?id=52695"
        self.assertEqual(mod._extract_person_id(url), "52695")
        self.assertEqual(mod._extract_person_id("https://elitessuisses.unil.ch/personne.php"), "inconnu")

    def test_find_matches_partial_and_exact(self):
        rows = [
            {"nom": "Aa, von der", "prénom": "Albert", "URL": "https://example/a"},
            {"nom": "Aab", "prénom": "Alain", "URL": "https://example/b"},
        ]

        partial = mod.find_matches(rows, "Albert Aa", exact=False)
        self.assertEqual(len(partial), 1)
        self.assertEqual(partial[0]["nom"], "Aa, von der")

        exact_ok = mod.find_matches(rows, "Albert Aa, von der", exact=True)
        self.assertEqual(len(exact_ok), 1)

        exact_ko = mod.find_matches(rows, "Albert Aa", exact=True)
        self.assertEqual(len(exact_ko), 0)

    def test_build_markdown_contains_required_frontmatter(self):
        selected = {
            "nom": "Aa, von der",
            "prénom": "Albert",
            "dates": "1894-1978",
            "mandats": "5",
            "Projet": "ch",
        }
        details = {
            "profile_title": "Albert Aa, von der",
            "sections": [{"title": "Données biographiques", "text": "Nom : ..."}],
            "body_excerpt": "",
        }

        md = mod.build_markdown(
            selected=selected,
            details=details,
            query="Albert Aa, von der",
            csv_path=Path(".agents/skills/fetch-elitesuisse-person-details/assets/elitessuisses_personnes_A_Z.csv"),
            person_url="https://elitessuisses.unil.ch/personne.php?id=52695",
        )

        self.assertIn('title: "Albert Aa, von der"', md)
        self.assertIn('transformation_by: "skill fetch-elitesuisse-person-details"', md)
        self.assertIn("sources:", md)
        self.assertIn("## Page 1", md)
        self.assertIn("### Données biographiques", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)

