import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestDatePublicationSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tests_dir = Path(__file__).resolve().parent
        cls.repo_root = cls.tests_dir.parents[3]

        extractor_path = cls.tests_dir.parent / "scripts" / "pdf_to_md_extractor.py"
        if not extractor_path.exists():
            raise FileNotFoundError(f"Script introuvable: {extractor_path}")
        extractor_spec = importlib.util.spec_from_file_location("pdf_to_md_extractor", extractor_path)
        cls.extractor = importlib.util.module_from_spec(extractor_spec)
        assert extractor_spec.loader is not None
        extractor_spec.loader.exec_module(cls.extractor)

        db_path = cls.repo_root / ".agents" / "skills" / "manage-named-entities-db" / "scripts" / "db.py"
        if not db_path.exists():
            raise FileNotFoundError(f"Module DB introuvable: {db_path}")
        db_spec = importlib.util.spec_from_file_location("named_entities_db", db_path)
        cls.db_module = importlib.util.module_from_spec(db_spec)
        assert db_spec.loader is not None
        db_spec.loader.exec_module(cls.db_module)

    def _to_repo_rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.repo_root).as_posix()

    def test_pdf_date_publication_is_synced_to_source_table(self):
        """Given/When/Then: la date extraite doit mettre à jour la source PDF en base."""
        with tempfile.TemporaryDirectory(dir=self.tests_dir) as temp_dir:
            temp_dir_path = Path(temp_dir)
            pdf_path = temp_dir_path / "date-publication-sync.pdf"
            md_path = temp_dir_path / "date-publication-sync.md"
            sqlite_path = temp_dir_path / "test_date_publication.sqlite"

            # Fichier factice suffisant car l'extraction est simulée dans le test.
            pdf_path.write_bytes(b"%PDF-1.4\n%unit-test\n")

            con = self.db_module.get_connection(sqlite_path)
            try:
                self.db_module.register_source_document(
                    con,
                    origin_path=pdf_path,
                    identifiant_source="test-date-publication",
                    titre="Test date publication",
                    date_publication="0000-00-00",
                )
                row_before = con.execute(
                    """
                    SELECT s.date_publication
                    FROM source s
                    JOIN source_document sd ON sd.source_id = s.id
                    WHERE sd.path = ?
                    LIMIT 1
                    """,
                    (self._to_repo_rel(pdf_path),),
                ).fetchone()
                self.assertIsNotNone(row_before)
                self.assertEqual("0000-00-00", row_before["date_publication"])
            finally:
                con.close()

            def _get_test_connection():
                return self.db_module.get_connection(sqlite_path)

            fake_local_result = {
                "markdown_body": "Pages détectées: 1\n\n## Page 1\n\nTexte test.",
                "page_labels": ["1"],
                "ocr_pages": 0,
                "pdf_metadata": {"CreationDate": "D:20200201010101+01'00'"},
                "selected_ocr_quality": 0.91,
            }

            with (
                patch.object(self.extractor, "_DB_AVAILABLE", True),
                patch.object(self.extractor, "_GET_DB_CONNECTION", _get_test_connection),
                patch.object(self.extractor, "_UPSERT_SOURCE", self.db_module.upsert_source),
                patch.object(
                    self.extractor,
                    "_GET_SOURCE_WITH_DOCUMENTS_BY_PATH",
                    self.db_module.get_source_with_documents_by_path,
                ),
                patch.object(self.extractor, "_UPDATE_SOURCE_OCR_STATUS", self.db_module.update_source_ocr_status),
                patch.object(
                    self.extractor,
                    "_try_mistral_ocr_markdown",
                    return_value=(None, None, None, ["mistral_disabled_for_unit_test"]),
                ),
                patch.object(self.extractor, "_local_process_pdf", return_value=fake_local_result),
                patch.object(self.extractor, "_compute_language_distribution", return_value="fr:100"),
                patch.object(self.extractor, "_maybe_trigger_translation", return_value=None),
            ):
                self.extractor.process_pdf(
                    pdf_path,
                    page_numbers=[1],
                    md_path=md_path,
                    no_translate=True,
                    write_files=True,
                )

            con = self.db_module.get_connection(sqlite_path)
            try:
                row_after = con.execute(
                    """
                    SELECT s.date_publication
                    FROM source s
                    JOIN source_document sd ON sd.source_id = s.id
                    WHERE sd.path = ?
                    LIMIT 1
                    """,
                    (self._to_repo_rel(pdf_path),),
                ).fetchone()
                self.assertIsNotNone(row_after)
                self.assertEqual("2020-02-01", row_after["date_publication"])
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()

