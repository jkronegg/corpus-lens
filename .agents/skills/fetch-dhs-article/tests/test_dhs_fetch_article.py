import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def find_script_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        direct_candidate = parent / "dhs_fetch_article.py"
        if direct_candidate.is_file():
            return direct_candidate

        scripts_candidate = parent / "scripts" / "dhs_fetch_article.py"
        if scripts_candidate.is_file():
            return scripts_candidate

    raise FileNotFoundError(
        f"Impossible de localiser dhs_fetch_article.py depuis {current}"
    )


def load_dhs_fetch_module():
    script_path = find_script_path()
    scripts_dir = script_path.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    spec = importlib.util.spec_from_file_location("dhs_fetch_article", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module depuis {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class NumericTermMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_dhs_fetch_module()

    def test_normalize_numeric_id_ignores_leading_zeroes(self):
        self.assertEqual(self.module.normalize_numeric_id("024433"), "24433")
        self.assertEqual(self.module.normalize_numeric_id("24433"), "24433")
        self.assertEqual(self.module.normalize_numeric_id("000000"), "0")

    def test_is_numeric_term_accepts_only_digits(self):
        self.assertTrue(self.module.is_numeric_term("024433"))
        self.assertFalse(self.module.is_numeric_term("024433a"))
        self.assertFalse(self.module.is_numeric_term("24 433"))

    def test_row_match_score_prefers_exact_id_when_term_is_numeric(self):
        row = {"ID": "024433", "Lemma": "Wille", "URL": "/fr/articles/024433/"}
        score = self.module.row_match_score(row, "024433")
        self.assertEqual(score, 1000)

    def test_find_hits_in_catalogs_returns_hit_for_numeric_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "liste_personnes_f_utf8.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["ID", "Lemma", "Complement", "Precision", "URL"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ID": "024433",
                        "Lemma": "Wille",
                        "Complement": "Ulrich",
                        "Precision": "",
                        "URL": "/fr/articles/024433/2024-11-22/",
                    }
                )

            hits = self.module.find_hits_in_catalogs("024433", [csv_path], max_hits=1)

            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].article_id, "024433")
            self.assertEqual(hits[0].lemma, "Wille")
            self.assertEqual(hits[0].url, "https://hls-dhs-dss.ch/fr/articles/024433/2024-11-22/")


if __name__ == "__main__":
    unittest.main()



