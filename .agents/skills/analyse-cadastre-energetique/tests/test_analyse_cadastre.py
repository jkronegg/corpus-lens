#!/usr/bin/env python3
"""Tests unitaires du skill analyse-cadastre-energetique."""

from __future__ import annotations

import importlib.util
import io
import sqlite3
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPT = TESTS_DIR.parent / "scripts" / "analyse_cadastre_energetique.py"

QUESTIONS = [
    (
        "statistiques generales",
        "Statistiques generales",
        ["nb_batiments", "nb_communes", "co2_total_kg", "besoins_ch_total"],
    ),
    (
        "top 3 communes par co2",
        "Top 3 communes par CO2 direct",
        ["commune", "Yverdon-les-Bains", "Lausanne", "Nyon"],
    ),
    (
        "analyse mazout",
        "Analyse des batiments chauffes au mazout",
        ["nb_batiments", "co2_total_kg", "400.0", "200.0"],
    ),
]


def _load_module():
    spec = importlib.util.spec_from_file_location("analyse_cadastre_energetique", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le script teste: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


class AnalyseCadastreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir.cleanup)
        self.tmp_path = Path(self._tmp_dir.name)
        self.db_path = self.tmp_path / "cadastre-test.sqlite"
        self.schema_md_path = self.tmp_path / "schema.md"
        self.schema_md_path.write_text(
            "### 4.3.1 Registre énergétique des bâtiments vaudois (RegEner)\n"
            "Extrait de schéma de test.\n",
            encoding="utf-8",
        )
        self._create_fixture_db(self.db_path)

    @staticmethod
    def _create_fixture_db(db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE regener (
                    egid INTEGER,
                    ggdenr INTEGER,
                    ggdename TEXT,
                    id_empreinte TEXT,
                    genh1 TEXT,
                    genw1 TEXT,
                    gbauj INTEGER,
                    ener_epoque TEXT,
                    besoins_ch REAL,
                    besoins_ecs REAL,
                    co2_dir_tot REAL,
                    co2_indir_tot REAL,
                    gebf REAL
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO regener (
                    egid, ggdenr, ggdename, id_empreinte, genh1, genw1, gbauj,
                    ener_epoque, besoins_ch, besoins_ecs, co2_dir_tot, co2_indir_tot, gebf
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, 5586, "Yverdon-les-Bains", "empreinte-1", "Mazout", "Solaire", 1975, "1946-1980", 1200.0, 200.0, 300.0, 20.0, 150.0),
                    (2, 5586, "Yverdon-les-Bains", "empreinte-2", "Gaz", "Electrique", 1990, "1981-2000", 800.0, 120.0, 50.0, 10.0, 95.0),
                    (3, 5434, "Lausanne", "empreinte-3", "Mazout", "Bois", 1960, "1946-1980", 1000.0, 180.0, 100.0, 12.0, 125.0),
                    (4, 5724, "Nyon", "empreinte-4", "PAC", "Electrique", 2015, "2001-2020", 400.0, 80.0, 10.0, 5.0, 90.0),
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def _run_main(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = [str(SCRIPT), *args]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            old_argv = sys.argv
            try:
                sys.argv = argv
                return_code = MODULE.main()
            finally:
                sys.argv = old_argv
        return return_code, stdout.getvalue(), stderr.getvalue()

    def test_supported_questions_return_successful_output(self) -> None:
        for question, expected_intent, expected_fragments in QUESTIONS:
            with self.subTest(question=question):
                return_code, stdout, stderr = self._run_main(
                    "--question",
                    question,
                    "--db",
                    str(self.db_path),
                    "--schema-md",
                    str(self.schema_md_path),
                    "--skip-update",
                )

                self.assertEqual(return_code, 0, msg=stderr)
                self.assertIn(f"Intent: {expected_intent}", stdout)
                for fragment in expected_fragments:
                    self.assertIn(fragment, stdout)
                self.assertEqual(stderr, "")

    def test_unknown_question_returns_error_code_2(self) -> None:
        return_code, stdout, stderr = self._run_main(
            "--question",
            "question introuvable",
            "--db",
            str(self.db_path),
            "--schema-md",
            str(self.schema_md_path),
            "--skip-update",
        )

        self.assertEqual(return_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("[ERREUR] Question non reconnue.", stderr)

    def test_json_output_contains_rows(self) -> None:
        return_code, stdout, stderr = self._run_main(
            "--question",
            "top 2 communes par co2",
            "--db",
            str(self.db_path),
            "--schema-md",
            str(self.schema_md_path),
            "--skip-update",
            "--json",
        )

        self.assertEqual(return_code, 0, msg=stderr)
        self.assertIn("\nJSON:\n", stdout)
        self.assertIn('"intent": "Top 2 communes par CO2 direct"', stdout)
        self.assertIn('"row_count": 2', stdout)
        self.assertIn('"commune": "Yverdon-les-Bains"', stdout)

    def test_markdown_output_is_written(self) -> None:
        output_path = self.tmp_path / "rapport.md"
        return_code, stdout, stderr = self._run_main(
            "--question",
            "analyse mazout",
            "--db",
            str(self.db_path),
            "--schema-md",
            str(self.schema_md_path),
            "--skip-update",
            "--output",
            str(output_path),
        )

        self.assertEqual(return_code, 0, msg=stderr)
        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("## Question", content)
        self.assertIn("analyse mazout", content)
        self.assertIn("Analyse des batiments chauffes au mazout", content)
        self.assertIn("```text", content)
        self.assertIn("Sortie Markdown:", stdout)

    def test_sql_mode_rejects_non_select_queries(self) -> None:
        with self.assertRaises(ValueError):
            MODULE._plan_intent("sql: DELETE FROM regener")

    def test_ensure_db_updated_downloads_direct_gpkg_into_assets(self) -> None:
        assets_dir = self.tmp_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        db_target = assets_dir / "Cadastre_energetique_des_batiments_vaudois_103-VD.1.gpkg"
        self.assertFalse(db_target.exists())

        source_gpkg = self.tmp_path / "source-direct.gpkg"
        conn = sqlite3.connect(source_gpkg)
        try:
            conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, label TEXT)")
            conn.execute("INSERT INTO sample (label) VALUES ('ok')")
            conn.commit()
        finally:
            conn.close()

        def fake_urlretrieve(_url: str, destination: str | Path):
            shutil.copy2(source_gpkg, Path(destination))
            return str(destination), None

        original_urlretrieve = MODULE.urllib.request.urlretrieve
        try:
            MODULE.urllib.request.urlretrieve = fake_urlretrieve
            MODULE._ensure_db_updated(db_target, "https://example.invalid/direct-gpkg")
        finally:
            MODULE.urllib.request.urlretrieve = original_urlretrieve

        self.assertTrue(db_target.exists())
        self.assertGreater(db_target.stat().st_size, 0)
        downloaded_conn = sqlite3.connect(db_target)
        try:
            row = downloaded_conn.execute("SELECT label FROM sample LIMIT 1").fetchone()
        finally:
            downloaded_conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "ok")


if __name__ == "__main__":
    unittest.main()



