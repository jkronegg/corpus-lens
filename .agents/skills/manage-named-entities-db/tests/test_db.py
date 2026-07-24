from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "AGENTS.md").exists() and (parent / ".agents").is_dir():
            return parent
    raise RuntimeError(f"Impossible de localiser la racine du repo depuis: {current}")


REPO_ROOT = _resolve_repo_root()
DB_MODULE_PATH = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts" / "db.py"


def load_db_module():
    spec = importlib.util.spec_from_file_location("manage_named_entities_db", DB_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module: {DB_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DB = load_db_module()


class NamedEntitiesDbTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(dir=REPO_ROOT)
        self.workdir = Path(self.tmpdir.name)
        self.db_path = self.workdir / "named_entities.sqlite"
        self.con = DB.get_connection(self.db_path)

    def tearDown(self) -> None:
        self.con.close()
        self.tmpdir.cleanup()

    def _source_entry(self, *, signature_suffix: str = "1", origine: str = "sources/tests/source.md") -> dict:
        return {
            "signature": f"tech-{signature_suffix}",
            "identifiant_source": f"src-{signature_suffix}",
            "titre": f"Titre {signature_suffix}",
            "date_publication": "2020-01-01",
            "date_consultation": "2020-01-02",
            "origine": origine,
            "auteurs": ["Alice", "Bob"],
            "periodes": ["1900-1950"],
            "ISBN": "",
            "ISSN": "",
            "DOI": "",
            "URL": "",
            "langues": "fr",
            "type_source": "secondaire",
            "nombre_pages": 12,
            "categorie": "histoire",
            "extrait_brut": "Extrait",
            "resume": "Résumé",
        }

    def _create_person_and_source(self) -> tuple[int, dict]:
        person = DB.upsert_person(self.con, "Karl Egli", "Karl Egli", aliases=["Egli, Karl"])
        source = DB.upsert_source(self.con, self._source_entry())
        return person["person_id"], source

    def test_get_connection_initializes_schema(self) -> None:
        """La connexion initialise la base avec les bonnes tables et les clés étrangères activées"""
        self.assertEqual(self.con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        mention_columns = [row[1] for row in self.con.execute("PRAGMA table_info(mention)")]
        source_doc_columns = [row[1] for row in self.con.execute("PRAGMA table_info(source_document)")]
        source_columns = [row[1] for row in self.con.execute("PRAGMA table_info(source)")]
        self.assertIn("source_document_id", mention_columns)
        self.assertIn("parent_doc_id", source_doc_columns)
        self.assertIn("ocr_status", source_columns)
        self.assertIn("signature", source_columns)

    def test_get_connection_migrates_legacy_source_identifiant_technique_to_signature(self) -> None:
        legacy_db_path = self.workdir / "legacy_named_entities.sqlite"
        legacy_con = sqlite3.connect(legacy_db_path)
        try:
            legacy_con.executescript(
                """
                CREATE TABLE source (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifiant_technique TEXT NOT NULL UNIQUE,
                    identifiant_source TEXT NOT NULL UNIQUE,
                    titre TEXT NOT NULL,
                    date_publication TEXT NOT NULL DEFAULT '0000-00-00',
                    date_consultation TEXT NOT NULL DEFAULT '0000-00-00',
                    origine TEXT NOT NULL UNIQUE,
                    auteurs_json TEXT NOT NULL DEFAULT '[]',
                    periodes_json TEXT NOT NULL DEFAULT '[]',
                    isbn TEXT NOT NULL DEFAULT '',
                    issn TEXT NOT NULL DEFAULT '',
                    doi TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    langues TEXT,
                    type_source TEXT NOT NULL DEFAULT 'secondaire',
                    nombre_pages INTEGER NOT NULL DEFAULT -1,
                    categorie TEXT NOT NULL DEFAULT 'autre',
                    extrait_brut TEXT NOT NULL DEFAULT '',
                    resume TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '2020-01-01T00:00:00Z',
                    updated_at TEXT NOT NULL DEFAULT '2020-01-01T00:00:00Z'
                );
                INSERT INTO source (
                    identifiant_technique, identifiant_source, titre,
                    date_publication, date_consultation, origine,
                    auteurs_json, periodes_json, isbn, issn, doi, url,
                    langues, type_source, nombre_pages, categorie, extrait_brut, resume,
                    created_at, updated_at
                ) VALUES (
                    'legacy-signature', 'legacy-src', 'Titre legacy',
                    '2020-01-01', '2020-01-02', 'sources/tests/legacy.md',
                    '[]', '[]', '', '', '', '',
                    'fr', 'secondaire', 1, 'autre', '', '',
                    '2020-01-01T00:00:00Z', '2020-01-01T00:00:00Z'
                );
                """
            )
            legacy_con.commit()
        finally:
            legacy_con.close()

        migrated_con = DB.get_connection(legacy_db_path)
        try:
            source_columns = [row[1] for row in migrated_con.execute("PRAGMA table_info(source)")]
            self.assertIn("signature", source_columns)
            self.assertNotIn("identifiant_technique", source_columns)

            stored = migrated_con.execute(
                "SELECT signature, identifiant_source, ocr_status FROM source WHERE identifiant_source = ?",
                ("legacy-src",),
            ).fetchone()
            self.assertEqual(stored["signature"], "legacy-signature")
            self.assertEqual(stored["ocr_status"], "N")
        finally:
            migrated_con.close()

    def test_upsert_person_search_person_and_stats(self) -> None:
        """Une personne s'enregistre, se met à jour, est retrouvée par recherche, et les stats sont correctes"""
        created = DB.upsert_person(self.con, "Karl Egli", "Karl Egli", aliases=["Egli, Karl"])
        updated = DB.upsert_person(self.con, "Karl Egli", "Karl Egli (mis à jour)", aliases=["Colonel Egli"])

        self.assertEqual(created["action"], "created")
        self.assertEqual(updated["action"], "updated")

        results = DB.search_person(self.con, "Egli")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "karl_egli")
        self.assertEqual(results[0]["display_name"], "Karl Egli (mis à jour)")
        self.assertGreaterEqual(results[0]["mention_count"], 0)

        stats = DB.get_stats(self.con)
        self.assertEqual(stats["persons"], 1)
        self.assertEqual(stats["mentions"], 0)

    def test_register_source_document_and_list_sources(self) -> None:
        """Une source s'enregistre comme source et comme document; un document dérivé s'enregistre comme un document; les parents sont gérés"""
        origin = self.workdir / "downloaded" / "source.md"
        origin.parent.mkdir(parents=True, exist_ok=True)
        origin.write_text("# Titre\n\nContenu", encoding="utf-8")
        derived = origin.with_name("source.translated.md")
        derived.write_text("# Titre traduit\n\nContenu", encoding="utf-8")

        result = DB.register_source_document(
            self.con,
            origin_path=origin,
            identifiant_source="downloaded-1",
            titre="Document téléchargé",
            url="https://example.invalid/doc",
            auteurs=["Alice"],
            periodes=["1914-1918"],
            isbn="123",
            issn="456",
            doi="10.1234/example",
            langues="de",
            type_source="primaire",
            nombre_pages=2,
            categorie="archive",
            extrait_brut="Extrait",
            resume="Résumé",
            ner_status=0
        )

        derived_result = DB.register_source_document(
            self.con,
            origin_path=derived,
            parent_path=origin,
            author="Traducteur",
            ner_status=1
        )

        self.assertEqual(result["action"], "created")
        self.assertIn("document_id", result)
        self.assertNotIn("documents_count", result)
        self.assertEqual(derived_result["action"], "created")
        self.assertEqual(derived_result["source_id"], result["source_id"])

        sources = DB.list_sources(self.con)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["signature"], DB._md5_file(origin))
        self.assertEqual(sources[0]["identifiant_source"], "downloaded-1")
        self.assertEqual(sources[0]["origine"], origin.resolve().relative_to(REPO_ROOT).as_posix())
        self.assertEqual(sources[0]["ocr_status"], "N")

        source_documents = self.con.execute(
            "SELECT id, path, parent_doc_id, source_id, ner_status FROM source_document ORDER BY path"
        ).fetchall()
        self.assertEqual(len(source_documents), 2)

        origin_row, derived_row = source_documents
        self.assertEqual(origin_row["path"], origin.resolve().relative_to(REPO_ROOT).as_posix())
        self.assertEqual(origin_row["ner_status"], 0)
        self.assertIsNone(origin_row["parent_doc_id"])

        self.assertEqual(derived_row["path"], derived.resolve().relative_to(REPO_ROOT).as_posix())
        self.assertEqual(derived_row["ner_status"], 1)
        self.assertEqual(derived_row["parent_doc_id"], origin_row["id"])
        self.assertEqual(derived_row["source_id"], origin_row["source_id"])

    def test_add_mention_resolves_source_document_and_lists_mentions(self) -> None:
        """Une mention ne peut être ajoutée qu'une fois (idempotence)"""
        self._create_person_and_source()
        origin_path = self._source_entry()["origine"]

        mention = DB.add_mention(
            self.con,
            person_key="Karl Egli",
            source=origin_path,
            page=3,
            line_start=12,
            line_end=14,
            quote="Egli",
            event_date="1916-01-11",
            extractor="manual",
            confidence=0.95,
        )
        duplicate = DB.add_mention(
            self.con,
            person_key="Karl Egli",
            source=origin_path,
            page=3,
            line_start=12,
            line_end=14,
            quote="Egli",
            event_date="1916-01-11",
            extractor="manual",
            confidence=0.95,
        )

        self.assertEqual(mention["action"], "created")
        self.assertEqual(duplicate["action"], "skipped")
        self.assertIsNotNone(mention["mention_id"])

        source_document_id = self.con.execute(
            "SELECT id FROM source_document WHERE path = ?",
            (origin_path,),
        ).fetchone()[0]
        stored = self.con.execute(
            "SELECT source, source_document_id FROM mention WHERE id = ?",
            (mention["mention_id"],),
        ).fetchone()
        self.assertEqual(stored["source"], origin_path)
        self.assertEqual(stored["source_document_id"], source_document_id)
        self.assertTrue(DB.source_has_mentions(self.con, origin_path))

        mentions = DB.list_mentions(self.con, person_key="Karl Egli")
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]["source_path"], origin_path)
        self.assertEqual(mentions[0]["source_document_id_resolved"], source_document_id)

        stats = DB.get_stats(self.con)
        self.assertEqual(stats["mentions"], 1)
        self.assertEqual(stats["mentioned_source_paths"], 1)
        self.assertEqual(stats["source_documents"], 1)

    def test_export_person_and_merge_persons(self) -> None:
        DB.upsert_person(self.con, "Karl Egli", "Karl Egli", aliases=["Egli, Karl"])
        DB.upsert_person(self.con, "Paul Egli", "Paul Egli", aliases=["Capitaine Egli"])
        DB.upsert_source(self.con, self._source_entry())
        DB.add_mention(
            self.con,
            person_key="Karl Egli",
            source=self._source_entry()["origine"],
            page=1,
            quote="Egli",
        )

        before = DB.export_person(self.con, "Karl Egli")
        self.assertIsNotNone(before)
        self.assertEqual(before["mention_count"], 1)
        self.assertEqual(len(before["mentions"]), 1)

        merged = DB.merge_persons(self.con, source_key="Karl Egli", target_key="Paul Egli")
        self.assertEqual(merged["action"], "merged")
        self.assertEqual(merged["mentions_moved"], 1)
        self.assertIn("Karl Egli", merged["aliases_added"])

        source_person = DB.export_person(self.con, "Karl Egli")
        target_person = DB.export_person(self.con, "Paul Egli")
        self.assertIsNone(source_person)
        self.assertIsNotNone(target_person)
        self.assertEqual(target_person["mention_count"], 1)
        self.assertEqual(len(target_person["mentions"]), 1)
        self.assertIn("Karl Egli", target_person["aliases_names"])

        stats = DB.get_stats(self.con)
        self.assertEqual(stats["persons"], 1)
        self.assertEqual(stats["mentions"], 1)

    def test_reset_ner_analysis_clears_entities_mentions_and_resets_status(self) -> None:
        DB.upsert_person(self.con, "Karl Egli", "Karl Egli")
        src = self._source_entry(signature_suffix="reset", origine="sources/tests/reset.md")
        DB.upsert_source(self.con, src)

        self.con.execute(
            "UPDATE source_document SET ner_status = 2 WHERE path = ?",
            (src["origine"],),
        )
        self.con.commit()

        mention = DB.add_mention(
            self.con,
            person_key="Karl Egli",
            source=src["origine"],
            page=1,
            quote="Egli",
        )
        self.assertEqual(mention["action"], "created")

        result = DB.reset_ner_analysis(self.con)
        self.assertEqual(result["action"], "reset_ner_analysis")
        self.assertEqual(result["deleted_mentions"], 1)
        self.assertEqual(result["deleted_persons"], 1)
        self.assertEqual(result["deleted_named_entities"], 1)
        self.assertEqual(result["updated_source_documents"], 1)

        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM mention").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM person").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM named_entity").fetchone()[0], 0)
        self.assertEqual(
            self.con.execute(
                "SELECT ner_status FROM source_document WHERE path = ?",
                (src["origine"],),
            ).fetchone()[0],
            1,
        )

    def test_replace_sources_rebuilds_deterministically(self) -> None:
        DB.replace_sources(
            self.con,
            [
                self._source_entry(signature_suffix="b", origine="sources/tests/b.md"),
                self._source_entry(signature_suffix="a", origine="sources/tests/a.md"),
            ],
        )

        sources = DB.list_sources(self.con)
        self.assertEqual([s["signature"] for s in sources], ["tech-a", "tech-b"])
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM source_document").fetchone()[0], 2)

        stats = DB.get_stats(self.con)
        self.assertEqual(stats["sources"], 2)
        self.assertEqual(stats["source_documents"], 2)

    def test_upsert_source_defaults_ocr_status_by_extension_and_preserves_existing_value(self) -> None:
        pdf_entry = self._source_entry(signature_suffix="pdf", origine="sources/tests/source.pdf")
        created = DB.upsert_source(self.con, pdf_entry)
        self.assertEqual(created["action"], "created")

        stored_status = self.con.execute(
            "SELECT ocr_status FROM source WHERE signature = ?",
            (pdf_entry["signature"],),
        ).fetchone()[0]
        self.assertEqual(stored_status, "P")

        DB.update_source_ocr_status(self.con, created["source_id"], "D")
        pdf_entry_updated = dict(pdf_entry)
        pdf_entry_updated["titre"] = "Titre mis à jour"
        pdf_entry_updated["ocr_status"] = "P"
        DB.upsert_source(self.con, pdf_entry_updated)

        preserved_status = self.con.execute(
            "SELECT ocr_status FROM source WHERE id = ?",
            (created["source_id"],),
        ).fetchone()[0]
        self.assertEqual(preserved_status, "D")

        md_entry = self._source_entry(signature_suffix="md", origine="sources/tests/source.md")
        DB.upsert_source(self.con, md_entry)
        md_status = self.con.execute(
            "SELECT ocr_status FROM source WHERE signature = ?",
            (md_entry["signature"],),
        ).fetchone()[0]
        self.assertEqual(md_status, "N")

    def test_replace_sources_keeps_existing_ocr_status(self) -> None:
        entry = self._source_entry(signature_suffix="keep", origine="sources/tests/keep.pdf")
        created = DB.upsert_source(self.con, entry)
        DB.update_source_ocr_status(self.con, created["source_id"], "T")

        DB.replace_sources(self.con, [entry])

        status = self.con.execute(
            "SELECT ocr_status FROM source WHERE signature = ?",
            (entry["signature"],),
        ).fetchone()[0]
        self.assertEqual(status, "T")


if __name__ == "__main__":
    unittest.main()


