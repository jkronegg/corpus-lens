#!/usr/bin/env python3
"""Tests unitaires pour fetch_wikipedia_article.py."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "fetch_wikipedia_article.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_wikipedia_article", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_module()


class FetchWikipediaArticleTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(mod.slugify("Affaire des colonels"), "affaire_des_colonels")

    def test_html_to_markdown_basic(self):
        html = """
        <div class="mw-parser-output">
          <p>Premier paragraphe avec <b>gras</b>.</p>
          <h2>Section 1</h2>
          <p>Second paragraphe.</p>
          <ul><li>Point A</li><li>Point B</li></ul>
        </div>
        """
        md = mod.html_to_markdown(html)
        self.assertIn("Premier paragraphe", md)
        self.assertIn("## Section 1", md)
        self.assertIn("- Point A", md)

    def test_html_to_markdown_references_section(self):
        html = """
        <div class="mw-parser-output">
          <p>Texte avec source<sup class="reference" id="cite_ref-1"><a href="#cite_note-1">[1]</a></sup>.</p>
          <h2><span id="Références">Références</span></h2>
          <div class="mw-references-wrap">
            <ol class="references">
              <li id="cite_note-1"><span class="reference-text"><a href="/wiki/Exemple">Source A</a> (<a href="https://web.archive.org/web/20200101000000/https://example.org">archive</a>)</span></li>
              <li id="cite_note-2"><span class="reference-text">Source B</span></li>
            </ol>
          </div>
        </div>
        """
        md = mod.html_to_markdown(html)
        self.assertIn("Texte avec source[1](#ref-1).", md)
        self.assertIn("## Références", md)
        self.assertIn("1. <a id=\"ref-1\"></a> [Source A](https://fr.wikipedia.org/wiki/Exemple)", md)
        self.assertIn("[archive](https://web.archive.org/web/20200101000000/https://example.org)", md)
        self.assertIn("2. <a id=\"ref-2\"></a> Source B", md)

    def test_html_to_markdown_keeps_section_titles(self):
        html = """
        <div class="mw-parser-output">
          <section>
            <h2>
              <span class="mw-headline" id="Violation_de_la_neutralité">Violation de la neutralité</span>
              <span class="mw-editsection">[modifier | modifier le code]</span>
            </h2>
            <p>Texte section.</p>
          </section>
        </div>
        """
        md = mod.html_to_markdown(html)
        self.assertIn("## Violation de la neutralité", md)
        self.assertNotIn("modifier le code", md)

    def test_build_markdown_contains_frontmatter(self):
        article = {
            "page_title": "Affaire des colonels",
            "page_url": "https://fr.wikipedia.org/wiki/Affaire_des_colonels",
            "api_url": "https://fr.wikipedia.org/w/api.php?...",
            "display_title": "<span>Affaire des colonels</span>",
        }
        md = mod.build_markdown("Affaire des colonels", "fr", article, "Contenu")
        self.assertIn('transformation_by: "skill fetch-wikipedia-article"', md)
        self.assertIn('language: "fr"', md)
        self.assertIn("## Page 1", md)
        self.assertIn("Contenu", md)

    def test_write_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "test.md"
            mod.write_output(out, "hello")
            self.assertEqual(out.read_text(encoding="utf-8"), "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)

