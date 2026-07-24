#!/usr/bin/env python3
"""Unit tests for swissvote_fetch_votation_sources.py helpers."""

from pathlib import Path
import sys
import tempfile
import unittest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import swissvote_fetch_votation_sources as mod  # noqa: E402


class TestSwissvoteFetchVotationSources(unittest.TestCase):
    def test_extract_official_links_from_html(self) -> None:
        html = """
        <html><body>
          <a class="bk_chrono" href="https://example.org/chrono.html">Link</a>
          <a class="federal-council-message" href="/vote/123.00/botschaft-de.pdf">PDF</a>
        </body></html>
        """
        chrono, message, debate, voting_text, results_by_domain = mod._extract_official_links_from_html(
            html,
            "https://swissvotes.ch/vote/123.00",
        )
        self.assertEqual(chrono, "https://example.org/chrono.html")
        self.assertEqual(message, "https://swissvotes.ch/vote/123.00/botschaft-de.pdf")
        self.assertIsNone(debate)
        self.assertIsNone(voting_text)
        self.assertIsNone(results_by_domain)

    def test_extract_french_alternate_url(self) -> None:
        html = """
        <html><head>
          <link rel="alternate" type="text/html" href="/ch/f/pore/rf/cr/2018/20180292.html" hreflang="fr" lang="fr" />
        </head><body></body></html>
        """
        fr_url = mod._extract_french_alternate_url(
            html,
            "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
        )
        self.assertEqual(fr_url, "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html")

    def test_extract_french_alternate_url_from_anchor(self) -> None:
        html = """
        <html><body>
          <a rel="alternate" href="https://swissvotes.ch/locale/fr_CH?return-to=abc" lang="fr" hreflang="fr">fr</a>
        </body></html>
        """
        fr_url = mod._extract_french_alternate_url(
            html,
            "https://swissvotes.ch/vote/639.00",
        )
        self.assertEqual(fr_url, "https://swissvotes.ch/locale/fr_CH?return-to=abc")

    def test_derive_french_url_from_german_path(self) -> None:
        de_url = "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html"
        fr_url = mod._derive_french_url_from_german_path(de_url)
        self.assertEqual(fr_url, "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html")

    def test_is_probably_same_document(self) -> None:
        self.assertTrue(
            mod._is_probably_same_document(
                "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
                "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html",
            )
        )
        self.assertFalse(
            mod._is_probably_same_document(
                "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
                "https://www.bk.admin.ch/bk/fr/home/droits-politiques/initiatives-populaires.html",
            )
        )

    def test_extract_official_links_fallback(self) -> None:
        links = [
            mod.ExtractedLink("Offizielle Chronologie", "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html"),
            mod.ExtractedLink("Botschaft des Bundesrats", "https://swissvotes.ch/vote/639.00/botschaft-de.pdf"),
        ]
        chrono, message, debate, voting_text, results_by_domain = mod._extract_official_links_fallback(links)
        self.assertIsNotNone(chrono)
        self.assertIn("bk.admin.ch", str(chrono))
        self.assertIsNotNone(message)
        self.assertIn("botschaft", str(message))
        self.assertIsNone(debate)
        self.assertIsNone(voting_text)
        self.assertIsNone(results_by_domain)

    def test_extract_official_links_fallback_french_chronology_url(self) -> None:
        links = [
            mod.ExtractedLink("Lien", "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html"),
            mod.ExtractedLink("PDF", "https://swissvotes.ch/vote/639.00/botschaft-fr.pdf"),
        ]
        chrono, message, _debate, _voting_text, _results_by_domain = mod._extract_official_links_fallback(links)
        self.assertEqual(chrono, "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html")
        self.assertIsNotNone(message)
        self.assertIn("botschaft", str(message))

    def test_convert_chronology_html_to_markdown(self) -> None:
        html = """
        <html><body>
          <h2>Bundesgesetz XYZ<br/>Chronologie</h2>
          <table>
            <tr><td>Chronologie</td><td>Datum</td><td>Fundstelle</td></tr>
            <tr><td>Abgestimmt am</td><td>07.03.2021</td><td>BBl 2021 1185</td></tr>
          </table>
        </body></html>
        """
        markdown = mod._convert_chronology_html_to_markdown(
            html,
            "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
            639,
        )
        self.assertIn("# Chronologie officielle - Votation 639.00", markdown)
        self.assertIn("## Tableau de chronologie", markdown)
        self.assertIn("| Chronologie | Date | Reference |", markdown)
        self.assertIn("| Abgestimmt am | 07.03.2021 | BBl 2021 1185 |", markdown)

    def test_render_vote_markdown_from_key_value_tables(self) -> None:
        html = """
        <html><body>
          <table class="collapsible">
            <thead><tr><th colspan="2">Informations generales</th></tr></thead>
            <tbody>
              <tr><th class="column-30">Titre officiel</th><td>Loi XYZ</td></tr>
              <tr><th class="column-30">Chronologie officielle</th><td><a href="/ch/f/pore/rf/cr/2018/20180292.html">Lien</a></td></tr>
            </tbody>
          </table>
        </body></html>
        """
        markdown = mod._render_markdown("https://swissvotes.ch/vote/999.00", html, 999)
        self.assertIn("## Donnees structurees (tableaux cle/valeur)", markdown)
        self.assertIn("### Informations generales", markdown)
        self.assertIn("| Cle | Valeur |", markdown)
        self.assertIn("| Titre officiel | Loi XYZ |", markdown)
        self.assertIn("[Lien](https://swissvotes.ch/ch/f/pore/rf/cr/2018/20180292.html)", markdown)

    def test_signature_uses_file_content_md5(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "doc_a.pdf"
            second = root / "doc_b.pdf"
            first.write_bytes(b"contenu-identique")
            second.write_bytes(b"contenu-identique")

            self.assertEqual(mod._md5_file(first), mod._md5_file(second))

            entry_a = mod._build_source_entry_from_family(
                votation_id=999,
                family="message_conseil_federal",
                items=[(first, "message_conseil_federal", "https://example.org/a.pdf")],
            )
            entry_b = mod._build_source_entry_from_family(
                votation_id=999,
                family="message_conseil_federal",
                items=[(second, "message_conseil_federal", "https://example.org/b.pdf")],
            )

            self.assertIsNotNone(entry_a)
            self.assertIsNotNone(entry_b)
            self.assertEqual(entry_a["signature"], entry_b["signature"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

