import importlib.util
import sys
import tempfile
import unittest
import warnings
from pathlib import Path


warnings.simplefilter("ignore", ResourceWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)


class DummyChecker:
    backend_name = "dummy"

    def __init__(self, accepted_words):
        self.accepted_words = {word.lower() for word in accepted_words}

    def check(self, word: str) -> bool:
        return word.lower() in self.accepted_words


class AcceptAllChecker:
    backend_name = "dummy-all"

    def check(self, word: str) -> bool:
        return True


class TestEstimateOcrQualityHunspell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current_dir = Path(__file__).resolve().parent
        script_path = cls.current_dir.parent / "scripts" / "estimate_ocr_quality_hunspell.py"
        spec = importlib.util.spec_from_file_location("estimate_ocr_quality_hunspell", script_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_markdown_cleanup_removes_front_matter_and_table_separators(self):
        markdown = """---
titre: \"Test\"
source: \"x.pdf\"
---

Pages détectées: 1-2

## Page 1

[header]: # (Préavis communal)

| Nom | Valeur |
| --- | --- |
| Bonjour | Monde |
"""

        cleaned = self.module._markdown_to_text(markdown)

        self.assertNotIn("titre:", cleaned)
        self.assertNotIn("Pages détectées", cleaned)
        self.assertNotIn("## Page", cleaned)
        self.assertNotIn("| --- |", cleaned)
        self.assertIn("Préavis communal", cleaned)
        self.assertIn("Bonjour", cleaned)

    def test_clean_text_scores_higher_than_garbled_text(self):
        checker = DummyChecker(
            {
                "bonjour", "tout", "le", "monde", "ceci", "est", "un", "texte", "communal",
                "préavis", "municipal", "saint", "george", "investissement", "solidaire",
            }
        )
        clean_text = "Bonjour tout le monde. Ceci est un texte communal. Préavis municipal de Saint-George."
        garbled_text = "B0nj0ur t0ut l3 m0nde. Pr3av1s muniCIPA l ace ptat1on inves tisse ment xx99999."

        clean_report = self.module.analyze_text(clean_text, checker)
        garbled_report = self.module.analyze_text(garbled_text, checker)

        self.assertGreater(clean_report.quality_score, garbled_report.quality_score)
        self.assertGreater(clean_report.spell_ratio, garbled_report.spell_ratio)

    def test_can_load_minimal_spylls_hunspell_dictionary(self):
        if self.module.SpyllsDictionary is None:
            self.skipTest("spylls non disponible")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "fr.aff").write_text(
                "SET UTF-8\n"
                "TRY esaitnrulodcpmvqfbghjxyzk\n",
                encoding="utf-8",
            )
            (tmp_path / "fr.dic").write_text(
                "3\n"
                "bonjour\n"
                "monde\n"
                "préavis\n",
                encoding="utf-8",
            )

            checker, aff_path, dic_path = self.module.load_spellchecker(dict_dir=tmp_path, lang="fr")

            self.assertTrue(checker.check("bonjour"))
            self.assertTrue(checker.check("monde"))
            self.assertFalse(checker.check("inconnu"))
            self.assertEqual(aff_path.name, "fr.aff")
            self.assertEqual(dic_path.name, "fr.dic")

    def test_reference_markdown_is_analyzable(self):
        repeated_line = "Le Conseil communal examine le preavis municipal et vote la decision finale."
        body = "\n".join([repeated_line for _ in range(60)])
        markdown = (
            "---\n"
            "titre: \"Reference\"\n"
            "source: \"reference.pdf\"\n"
            "---\n\n"
            "Pages detectees: 1\n\n"
            "## Page 1\n\n"
            f"{body}\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_path = Path(tmp_dir) / "reference.md"
            sample_path.write_text(markdown, encoding="utf-8")
            report = self.module.analyze_markdown_file(sample_path, AcceptAllChecker())

        self.assertGreater(report.token_count, 300)
        self.assertGreater(report.checked_words, 200)
        self.assertGreaterEqual(report.quality_score, 0.0)
        self.assertLessEqual(report.quality_score, 1.0)


if __name__ == "__main__":
    unittest.main()

