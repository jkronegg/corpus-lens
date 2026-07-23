#!/usr/bin/env python3
"""Smoke tests for swissvote_fetch_votation_sources.py helpers."""

from pathlib import Path
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import swissvote_fetch_votation_sources as mod  # noqa: E402


def test_extract_official_links_from_html() -> None:
    html = """
    <html><body>
      <a class="bk_chrono" href="https://example.org/chrono.html">Link</a>
      <a class="federal-council-message" href="/vote/123.00/botschaft-de.pdf">PDF</a>
    </body></html>
    """
    chrono, message = mod._extract_official_links_from_html(html, "https://swissvotes.ch/vote/123.00")
    assert chrono == "https://example.org/chrono.html"
    assert message == "https://swissvotes.ch/vote/123.00/botschaft-de.pdf"


def test_extract_french_alternate_url() -> None:
    html = """
    <html><head>
      <link rel="alternate" type="text/html" href="/ch/f/pore/rf/cr/2018/20180292.html" hreflang="fr" lang="fr" />
    </head><body></body></html>
    """
    fr_url = mod._extract_french_alternate_url(
        html,
        "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
    )
    assert fr_url == "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html"


def test_extract_french_alternate_url_from_anchor() -> None:
    html = """
    <html><body>
      <a rel="alternate" href="https://swissvotes.ch/locale/fr_CH?return-to=abc" lang="fr" hreflang="fr">fr</a>
    </body></html>
    """
    fr_url = mod._extract_french_alternate_url(
        html,
        "https://swissvotes.ch/vote/639.00",
    )
    assert fr_url == "https://swissvotes.ch/locale/fr_CH?return-to=abc"


def test_derive_french_url_from_german_path() -> None:
    de_url = "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html"
    fr_url = mod._derive_french_url_from_german_path(de_url)
    assert fr_url == "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html"


def test_is_probably_same_document() -> None:
    assert mod._is_probably_same_document(
        "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
        "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html",
    )
    assert not mod._is_probably_same_document(
        "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html",
        "https://www.bk.admin.ch/bk/fr/home/droits-politiques/initiatives-populaires.html",
    )


def test_extract_official_links_fallback() -> None:
    links = [
        mod.ExtractedLink("Offizielle Chronologie", "https://www.bk.admin.ch/ch/d/pore/rf/cr/2018/20180292.html"),
        mod.ExtractedLink("Botschaft des Bundesrats", "https://swissvotes.ch/vote/639.00/botschaft-de.pdf"),
    ]
    chrono, message = mod._extract_official_links_fallback(links)
    assert chrono and "bk.admin.ch" in chrono
    assert message and "botschaft" in message


def test_extract_official_links_fallback_french_chronology_url() -> None:
    links = [
        mod.ExtractedLink("Lien", "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html"),
        mod.ExtractedLink("PDF", "https://swissvotes.ch/vote/639.00/botschaft-fr.pdf"),
    ]
    chrono, message = mod._extract_official_links_fallback(links)
    assert chrono == "https://www.bk.admin.ch/ch/f/pore/rf/cr/2018/20180292.html"
    assert message and "botschaft" in message


def test_convert_chronology_html_to_markdown() -> None:
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
    assert "# Chronologie officielle - Votation 639.00" in markdown
    assert "## Tableau de chronologie" in markdown
    assert "| Chronologie | Date | Reference |" in markdown
    assert "| Abgestimmt am | 07.03.2021 | BBl 2021 1185 |" in markdown


def test_render_vote_markdown_from_key_value_tables() -> None:
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
    assert "## Donnees structurees (tableaux cle/valeur)" in markdown
    assert "### Informations generales" in markdown
    assert "| Cle | Valeur |" in markdown
    assert "| Titre officiel | Loi XYZ |" in markdown
    assert "[Lien](https://swissvotes.ch/ch/f/pore/rf/cr/2018/20180292.html)" in markdown


def test_signature_uses_file_content_md5() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        first = root / "doc_a.pdf"
        second = root / "doc_b.pdf"
        first.write_bytes(b"contenu-identique")
        second.write_bytes(b"contenu-identique")

        assert mod._md5_file(first) == mod._md5_file(second)

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

        assert entry_a is not None
        assert entry_b is not None
        assert entry_a["signature"] == entry_b["signature"]


def main() -> int:
    test_extract_official_links_from_html()
    test_extract_french_alternate_url()
    test_extract_french_alternate_url_from_anchor()
    test_derive_french_url_from_german_path()
    test_is_probably_same_document()
    test_extract_official_links_fallback()
    test_extract_official_links_fallback_french_chronology_url()
    test_convert_chronology_html_to_markdown()
    test_render_vote_markdown_from_key_value_tables()
    test_signature_uses_file_content_md5()
    print("OK: smoke_test_swissvote_fetch_votation_sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

