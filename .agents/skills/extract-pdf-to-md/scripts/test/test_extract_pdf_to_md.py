import importlib.util
import os
import re
import unittest
from pathlib import Path


class TestExtractPanda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current_dir = Path(__file__).resolve().parent
        script_path = cls.current_dir / "../pdf_to_md_extractor.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Script introuvable: {script_path}")
        spec = importlib.util.spec_from_file_location("pdf_to_md_extractor", script_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    @staticmethod
    def _normalize_for_table_assertion(value: str) -> str:
        value = value or ""
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"\s*<br>\s*", "<br>", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def assert_pdf_page_contains_text(self, pdf_filename, page_numbers, expected_text_included, *, normalize=False):
        pdf_path = self.current_dir / pdf_filename
        self.assertTrue(pdf_path.exists(), f"PDF introuvable: {pdf_filename}")

        previous_cwd = Path.cwd()
        try:
            os.chdir(self.current_dir)
            text = self.module.process_pdf(pdf_filename, page_numbers, write_files=False)
        finally:
            os.chdir(previous_cwd)
        print(text)

        haystack = self._normalize_for_table_assertion(text) if normalize else text

        if isinstance(expected_text_included, list):
            for expected_fragment in expected_text_included:
                needle = self._normalize_for_table_assertion(expected_fragment) if normalize else expected_fragment
                self.assertIn(needle, haystack)
        else:
            needle = self._normalize_for_table_assertion(expected_text_included) if normalize else expected_text_included
            self.assertIn(needle, haystack)

    def test_one_column(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
            page_numbers=[1],
            expected_text_included="""Jusqu'à la guerre mondiale, le code pénal militaire de 1851, actuellement en vigueur, a pendant de longues années joué un rôle relativement effacé.""")

    def test_one_column2(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="Initiative_parlementaire_Lang_2006_suppression_justice_militaire.pdf",
            page_numbers=[2],
            expected_text_included="""30 de notre Constitution, ne déclare rien de tel. Il est vrai que l'avis de notre collègue Lang repose, non""")

    def test_two_columns(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="debat_parlementaire.pdf",
            page_numbers=[1],
            expected_text_included="""M. Maunoir, rapporteur français de la majorité de la commission. Monsieur le président et Messieurs les députés. Le 8 août 1916, la direction du parti socialiste suisse a remis à la chancellerie fédérale une demande d'initiative concernant l'introduction d'un article58bis dans la constitution fédérale (suppression de la justice militaire), appuyée par 120.400 signatures, dont après vérification 118.996 ont été déclarées valables.""")

    def test_two_columns2(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="debat_parlementaire.pdf",
            page_numbers=[2],
            expected_text_included="""Le 12 mai 1916, le Conseil fédéral accordait au Général un droit de grâce spécial en matière militaire, droit qui revêtait le caractère d'une sorte de libération conditionnelle.""")

    def test_header(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="debat_parlementaire.pdf",
            page_numbers=[1],
            expected_text_included="""NATIONALRAT                  —  485              Aufhebung der Militärjustiz""")

    def test_hyphenation_basic(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
            page_numbers=[1],
            expected_text_included="""C'est la guerre actuelle qui, en imposant à la Suisse une mobilisation prolongée de son armée, a donn'é une importance nouvelle a,ux questions relatives au droit pénal et à la juridiction militaires.""")

    def test_hyphenation_words_with_dash(self):
        self.assertIn("contre-projet", self.module._dehyphenate_text("""contre-
projet"""))
        self.assertIn("c'est-à-dire", self.module._dehyphenate_text("""c'est-à-
dire"""))
        self.assertIn("elle-même", self.module._dehyphenate_text("""elle-
même"""))

    def test_hyphenation_exception_numbers(self):
        self.assertIn("vingt-cinq", self.module._dehyphenate_text("""vingt-
cinq"""))
        self.assertIn("quarante-et-un", self.module._dehyphenate_text("""quarante-et-
un"""))

    def test_ocr_result_renders_table_as_markdown(self):
        ocr_result = [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], "Nom", 0.99),
            ([[130, 10], [220, 10], [220, 30], [130, 30]], "Voix", 0.99),
            ([[250, 10], [360, 10], [360, 30], [250, 30]], "Statut", 0.99),
            ([[10, 40], [100, 40], [100, 60], [10, 60]], "Alice", 0.99),
            ([[130, 40], [220, 40], [220, 60], [130, 60]], "250", 0.99),
            ([[250, 40], [360, 40], [360, 60], [250, 60]], "Elue", 0.99),
            ([[10, 70], [100, 70], [100, 90], [10, 90]], "Bob", 0.99),
            ([[130, 70], [220, 70], [220, 90], [130, 90]], "180", 0.99),
            ([[250, 70], [360, 70], [360, 90], [250, 90]], "Non elu", 0.99),
        ]

        text = self.module._ocr_result_to_text_or_markdown(ocr_result)

        self.assertIn("| Nom | Voix | Statut |", text)
        self.assertIn("| --- | --- | --- |", text)
        self.assertIn("| Alice | 250 | Elue |", text)
        self.assertIn("| Bob | 180 | Non elu |", text)

    def test_ocr_result_without_table_remains_plain_text(self):
        ocr_result = [
            ([[10, 10], [260, 10], [260, 30], [10, 30]], "Commune de Saint-George", 0.99),
            ([[10, 42], [260, 42], [260, 62], [10, 62]], "Proces-verbal communal", 0.99),
        ]

        text = self.module._ocr_result_to_text_or_markdown(ocr_result)

        self.assertIn("Commune de Saint-George", text)
        self.assertIn("Proces-verbal communal", text)
        self.assertNotIn("| --- |", text)

    # ------------------------------------------------------------------
    # Tests: normalisation et détection du label de page
    # ------------------------------------------------------------------

    def test_normalize_page_label_strips_spaces(self):
        self.assertEqual(self.module._normalize_page_label("  42  "), "42")

    def test_normalize_page_label_replaces_em_dash(self):
        self.assertEqual(self.module._normalize_page_label("12–34"), "12-34")

    def test_normalize_page_label_collapses_spaces_around_dash(self):
        self.assertEqual(self.module._normalize_page_label("12 – 34"), "12-34")

    def test_normalize_page_label_empty(self):
        self.assertEqual(self.module._normalize_page_label(""), "")

    def test_next_page_label_increments(self):
        self.assertEqual(self.module._next_page_label("42", "1"), "43")

    def test_next_page_label_no_prev_uses_fallback(self):
        self.assertEqual(self.module._next_page_label("", "5"), "5")

    def test_next_page_label_none_uses_fallback(self):
        self.assertEqual(self.module._next_page_label(None, "7"), "7")

    def test_next_page_label_uses_last_number(self):
        # "12-34" → dernier numéro = 34, donc suivant = 35
        self.assertEqual(self.module._next_page_label("12-34", "1"), "35")

    def test_detect_page_label_dash_pattern_high_number(self):
        """Le motif — 485 — doit être extrait comme label."""
        text = "NATIONALRAT  — 485 — Aufhebung der Militärjustiz\nCorps du texte..."
        label = self.module._detect_page_label_from_text(text, "1")
        self.assertEqual(label, "485")

    def test_detect_page_label_standalone_number(self):
        """Un nombre à 3-4 chiffres seul sur une ligne est reconnu comme label."""
        text = "Titre du document\n\n349\n\nCorps du texte qui commence ici."
        label = self.module._detect_page_label_from_text(text, "1")
        self.assertEqual(label, "349")

    def test_detect_page_label_fallback(self):
        """Si aucun motif n'est trouvé, le fallback normalisé est retourné."""
        text = "Du texte quelconque sans numéro de page clairement identifiable."
        label = self.module._detect_page_label_from_text(text, "3")
        self.assertEqual(label, "3")

    def test_detect_page_label_low_number_ignored(self):
        """Un nombre bas (< 100) encadré de tirets ne doit pas être pris comme label
        (pour éviter de confondre avec un article de loi du type «— 1 —»)."""
        text = "— 5 — Titre de section\nCorps du texte."
        label = self.module._detect_page_label_from_text(text, "99")
        # Le chiffre 5 ne satisfait pas require_high_numbers → fallback
        self.assertEqual(label, "99")

    # ------------------------------------------------------------------
    # Tests: présence du titre ## Page X dans la sortie de process_pdf
    # ------------------------------------------------------------------

    def test_page_heading_number_from_header1(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="debat_parlementaire.pdf",
            page_numbers=[1],
            expected_text_included="""## Page 485""")

    def test_page_heading_number_from_header2(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
            page_numbers=[4],
            expected_text_included="""## Page 352""")

    def test_page_heading_number_from_body(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="message_conseil_federal.pdf",
            page_numbers=[1],
            expected_text_included="""## Page 681""")

    def test_narrow_character_spacing(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="brochure_explicative_officielle.pdf",
            page_numbers=[2],
            expected_text_included="""• Exécution des peines et des mesures: Dans les limites des principes fixés par la Confédérat~on. les cantons seront appelés dans une plus large mesure à accomplir ces tâches et à en assurer le financement.""")

# PDF de loi majoritairement à 2 colonnes, mais très peu d'espace entre les colonnes = dur à traiter
#     def test_narrow_character_spacing2(self):
#         self.assert_pdf_page_contains_text(
#             pdf_filename="code_penal_militaire_ff1927i805_1927-06-13_10084988.pdf",
#             page_numbers=[6],
#             expected_text_included="""Désistement et repentir actif.""")

    def test_table_basic(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="Wikipédia_Réarmement_Allemagne_sous_le_Troisième_Reich.pdf",
            page_numbers=[7],
            expected_text_included="|                                                           | Dépenses     | Dépenses      | Dépenses            | Dépenses            |\n"+
                                   "|                                                           | allemandes   | soviétiques   | allemandes          | soviétiques         |\n"+
                                   "|                                                           | (Mil. RM)    | 7             | 8                   | 9                   |\n"+
                                   "|                                                           |              | (Mil. Rbls)   | après ajustement*   | après ajustement*   |\n"+
                                   "|:----------------------------------------------------------|:-------------|:--------------|:--------------------|:--------------------|\n"+
                                   "| 1928                                                      | 0,75         | 0,88          | NA                  | NA                  |\n"+
                                   "| 1929                                                      | 0,69         | 1,05          | 0,69                | 1,05                |\n"+
                                   "| 1930                                                      | 0,67         | 1,20          | 0,73                | 1,12                |\n"+
                                   "| 1931                                                      | 0,61         | 1,79          | 0,75                | 1,43                |\n"+
                                   "| 1932                                                      | 0,69         | 1,05          | 0,98                | 0,70                |\n"+
                                   "| 1933                                                      | 0,62         | 4,03          | 0,91                | 2,46                |\n"+
                                   "| 1934                                                      | 4,09         | 5,40          | 5,7                 | 2,82                |\n"+
                                   "| 1935                                                      | 5,49         | 8,20          | 7,40                | 3,39                |\n"+
                                   "| 1936                                                      | 10,27        | 14,80         | 13,53               | 5,05                |\n"+
                                   "| 1937                                                      | 10,96        | 17,48         | 14,19               | 5,54                |\n"+
                                   "| 1938                                                      | 17,25        | 22,37         | 27,04               | 7,66                |\n"+
                                   "| 1939                                                      | 38,00        | 40,88         | 38,6                | 10,25               |\n"+
                                   "| *Ajustement dû à l'inflation calculé sur une base de 1929 | nan          | nan           | nan                 | nan                 |")

    def test_table_mixed(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="CODEBOOK.pdf",
            page_numbers=[4],
            expected_text_included=["""| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN | 
|-------|----------------|------------------|----------------------|
| Rechtsform | rechtsform | Rechtsform der Abstimmungsvorlage <br><br>1 Obligatorisches Referendum <br>2 Fakultatives Referendum <br>3 Volksinitiative <br>4 Direkter Gegenentwurf zu einer Volksinitiative <br>5 Stichfrage (seit 1987 bei Gegenüberstellung von Volksinitiati-<br>ven und Gegenentwürfen) | Schweizerische Bundeskanzlei (online). |"""],
            normalize=True,
        )

    def test_whitespace_between_words_is_not_hung(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="extrait-de-proces-verbal-1.pdf",
            page_numbers=[1],
            expected_text_included=["EXTRAIT DE PROCES-VERBAL DE LA SEANCE DU 23 SEPTEMBRE 2020"],
            normalize=True,
        )

    def test_frontmatter_yaml(self):
        self.assert_pdf_page_contains_text(
            pdf_filename="debat_parlementaire.pdf",
            page_numbers=[7],
            expected_text_included=["""---
titre: "debat parlementaire"
source: "debat_parlementaire.pdf"
date_extraction: """, """
pages: "1"
transformation_by: "skill extract-pdf-to-md"
language_distribution: "de:72, fr:28"
author: "skill extract-pdf-to-md"
---
"""])

    # def test_complex_table(self):
    #     # this test fails because the table is too complex:
    #     # - mono-column, but recognized as two columns
    #     # - bad character ordering which mixes the cell col/row order
    #     # - space as thousand separator
    #     self.assert_pdf_page_contains_text(
    #         pdf_filename="arrete_resultat.pdf",
    #         page_numbers=[3],
    #         expected_text_included=""" |    ZH  |   726118 | 1294 | 293660 | 40,4 | 11810 | 21 | 281829 | 185975 | 95854 | 1 |""")

    # def test_page_heading_number_from_next_pages_on_edge_cases_OCR_errors(self):
    #     # pages index 1 to 3 are wrongly recognized:
    #     # - index 1: OCR missed the correct page number 349
    #     # - index 2: OCR misread 850 when the correct page number is 350
    #     # - index 3: OCR misread 851 when the correct page number is 351
    #     self.assert_pdf_page_contains_text(
    #         pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
    #         page_numbers=[1],
    #         expected_text_included="""## Page 349""")
    #     self.assert_pdf_page_contains_text(
    #         pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
    #         page_numbers=[2],
    #         expected_text_included="""## Page 350""")
    #     self.assert_pdf_page_contains_text(
    #         pdf_filename="message_conseil_federal_ff1918v349_20181201_10081845.pdf",
    #         page_numbers=[3],
    #         expected_text_included="""## Page 351""")


    def test_page_heading_present_all_pages(self):
        """Chaque page du PDF doit produire exactement un titre ## Page X."""
        pdf_path = self.current_dir / "debat_parlementaire.pdf"
        self.assertTrue(pdf_path.exists(), "PDF introuvable: debat_parlementaire.pdf")
        previous_cwd = Path.cwd()
        page_numbers = [1,2,3]
        expected_count=len(page_numbers)
        try:
            os.chdir(self.current_dir)
            text = self.module.process_pdf("debat_parlementaire.pdf", page_numbers, write_files = False)
        finally:
            os.chdir(previous_cwd)
        headings = [line for line in text.split("\n") if line.startswith("## Page ")]
        self.assertEqual(
            len(headings), expected_count,
            f"Attendu {expected_count} titre(s) ## Page X, obtenu {len(headings)}"
        )



if __name__ == "__main__":
    unittest.main()

