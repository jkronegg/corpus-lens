#!/usr/bin/env python3
"""Tests unitaires pour fetch_dodis_persons_csv.py."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "fetch_dodis_persons_csv.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_dodis_persons_csv", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FetchDodisPersonsCsvTests(unittest.TestCase):
    def test_parse_given_and_years(self):
        first, birth, death = mod.parse_given_and_years("John (1900–1980)")
        self.assertEqual(first, "John")
        self.assertEqual(birth, "1900")
        self.assertEqual(death, "1980")

    def test_parse_given_without_years(self):
        first, birth, death = mod.parse_given_and_years("Jane")
        self.assertEqual(first, "Jane")
        self.assertEqual(birth, "")
        self.assertEqual(death, "")

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state = {
                "search_url": "https://dodis.ch/search?q=&c=Person&f=All&t=all&cb=doc",
                "last_completed_page": 42,
                "next_page_url": "https://dodis.ch/search?p=43",
                "rows_written": 840,
            }
            mod.save_state(state_path, state)
            loaded = mod.load_state(state_path)
            self.assertEqual(loaded["last_completed_page"], 42)
            self.assertEqual(loaded["rows_written"], 840)

    def test_load_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "persons.csv"
            csv_path.write_text(
                "prénom,nom,année de naissance,année de décès,URL\n"
                "John,Doe,1900,1980,https://dodis.ch/P1\n",
                encoding="utf-8",
            )
            rows = mod.load_existing_rows(csv_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["nom"], "Doe")


if __name__ == "__main__":
    unittest.main(verbosity=2)

