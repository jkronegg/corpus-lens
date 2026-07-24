"""
Tests unitaires pour sync_sources_json.py — Points 1 à 4 du README.md.

Point 1 : Correction des incohérences entre fichiers et base de données
          (fichiers supprimés, renommés, déplacés)
Point 2 : Extraction du texte PDF et conversion en Markdown
          (sections Page X, normalisation des en-têtes, stats)
Point 3 : Mise à jour de la base de données avec les métadonnées
          (dates, auteurs, catégories, identifiants bibliographiques)
Point 4 : Recherche d'entités nommées dans le texte Markdown
          (détection de la langue, sélection du Markdown français, NER)
"""

import sqlite3
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ajout de scripts/ au PYTHONPATH pour l'import du module testé
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import sync_sources_json as sut


# ===========================================================================
# Helpers partagés
# ===========================================================================

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "manage-named-entities-db"
    / "assets"
    / "schema.sql"
)
SCHEMA_SQL = _SCHEMA_PATH.read_text(encoding="utf-8")


def _make_db() -> sqlite3.Connection:
    """Crée une base SQLite en mémoire avec le schéma minimal requis."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    con.commit()
    return con


def _insert_source(con, *, origine: str, signature: str = "abc123") -> int:
    cur = con.execute(
        "INSERT INTO source (signature, identifiant_source, titre, origine) "
        "VALUES (?, ?, ?, ?)",
        (signature, f"SRC-{signature}", f"Titre {origine}", origine),
    )
    con.commit()
    return cur.lastrowid


def _insert_source_document(con, *, source_id: int, path: str, signature: str = "doc123") -> int:
    cur = con.execute(
        "INSERT INTO source_document (source_id, path, file_name, signature) "
        "VALUES (?, ?, ?, ?)",
        (source_id, path, Path(path).name, signature),
    )
    con.commit()
    return cur.lastrowid


def _md(tmp_path: Path, name: str, content: str) -> Path:
    """Écrit un fichier Markdown dans tmp_path et retourne son chemin."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class _TmpDirMixin(unittest.TestCase):
    """Mixin qui fournit self.tmp_path (Path) pour chaque méthode de test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)


# ===========================================================================
# POINT 1 — Correction des incohérences (suppressions, renommages, déplacements)
# ===========================================================================


class TestSyncDeletedFiles(_TmpDirMixin):
    """_sync_deleted_files détecte les documents dont le fichier a disparu."""

    def test_cycle_synchro_puis_suppression_fichier_nettoie_references(self):
        """Ajout fichier, synchro, suppression fichier, resynchro => références supprimées."""
        con = _make_db()
        real_file = self.tmp_path / "sources" / "cycle.md"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text("## Page 1\n\nContenu.\n", encoding="utf-8")

        rel_path = "sources/cycle.md"
        src_id = _insert_source(con, origine=rel_path, signature="sig-cycle")
        doc_id = _insert_source_document(con, source_id=src_id, path=rel_path, signature="doc-cycle")

        con.execute(
            "INSERT INTO named_entity (id, key, entity_type, display_name) VALUES (?, ?, ?, ?)",
            (1, "alice_dupont", "person", "Alice Dupont"),
        )
        con.execute(
            "INSERT INTO person (entity_id, key, display_name, aliases_names) VALUES (?, ?, ?, ?)",
            (1, "alice_dupont", "Alice Dupont", "[]"),
        )
        con.execute(
            "INSERT INTO named_entity (id, key, entity_type, display_name) VALUES (?, ?, ?, ?)",
            (2, "geneve", "place", "Genève"),
        )
        con.execute(
            "INSERT INTO mention (entity_id, source_document_id, source, page, extractor) VALUES (?, ?, ?, ?, ?)",
            (1, doc_id, rel_path, 1, "manual"),
        )
        con.execute(
            "INSERT INTO mention (entity_id, source_document_id, source, page, extractor) VALUES (?, ?, ?, ?, ?)",
            (2, doc_id, rel_path, 1, "manual"),
        )
        con.commit()

        with patch.object(sut, "ROOT", self.tmp_path):
            first_result = sut._sync_deleted_files(con)

            self.assertEqual(first_result["deleted"], 0)
            self.assertEqual(
                con.execute("SELECT COUNT(*) AS cnt FROM source WHERE origine = ?", (rel_path,)).fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                con.execute("SELECT COUNT(*) AS cnt FROM source_document WHERE path = ?", (rel_path,)).fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                con.execute("SELECT COUNT(*) AS cnt FROM mention WHERE source_document_id = ?", (doc_id,)).fetchone()["cnt"],
                2,
            )

            real_file.unlink()

            second_result = sut._sync_deleted_files(con)

        self.assertEqual(second_result["deleted"], 1)
        self.assertEqual(
            con.execute("SELECT COUNT(*) AS cnt FROM source WHERE origine = ?", (rel_path,)).fetchone()["cnt"],
            0,
        )
        self.assertEqual(
            con.execute("SELECT COUNT(*) AS cnt FROM source_document WHERE path = ?", (rel_path,)).fetchone()["cnt"],
            0,
        )
        self.assertEqual(
            con.execute("SELECT COUNT(*) AS cnt FROM mention WHERE source_document_id = ?", (doc_id,)).fetchone()["cnt"],
            0,
        )
        self.assertEqual(con.execute("SELECT COUNT(*) AS cnt FROM person").fetchone()["cnt"], 0)
        self.assertEqual(con.execute("SELECT COUNT(*) AS cnt FROM named_entity").fetchone()["cnt"], 0)

    def test_document_absent_est_supprime_de_source_document(self):
        """Un enregistrement source_document dont le fichier est absent est supprimé."""
        con = _make_db()
        src_id = _insert_source(con, origine="sources/doc.pdf")
        ghost_path = "sources/ghost.md"
        _insert_source_document(con, source_id=src_id, path=ghost_path)

        with patch.object(sut, "ROOT", self.tmp_path):
            result = sut._sync_deleted_files(con)

        rows = con.execute("SELECT id FROM source_document WHERE path = ?", (ghost_path,)).fetchall()
        self.assertEqual(rows, [], "Le document fantôme doit avoir été supprimé de source_document.")
        self.assertGreaterEqual(result["deleted"], 1)

    def test_document_present_est_conserve(self):
        """Un enregistrement source_document dont le fichier existe est conservé."""
        con = _make_db()
        src_id = _insert_source(con, origine="sources/doc.pdf")
        real_file = self.tmp_path / "sources" / "real.md"
        real_file.parent.mkdir(parents=True, exist_ok=True)
        real_file.write_text("## Page 1\n\nContenu.\n", encoding="utf-8")
        real_rel = "sources/real.md"
        _insert_source_document(con, source_id=src_id, path=real_rel)

        with patch.object(sut, "ROOT", self.tmp_path):
            result = sut._sync_deleted_files(con)

        rows = con.execute("SELECT id FROM source_document WHERE path = ?", (real_rel,)).fetchall()
        self.assertEqual(len(rows), 1, "Le document existant doit être conservé.")
        self.assertEqual(result["deleted"], 0)

    def test_source_associee_est_supprimee_quand_fichier_absent(self):
        """Quand le fichier principal d'une source disparaît, sa ligne source est supprimée."""
        con = _make_db()
        origine = "sources/rapport.md"
        src_id = _insert_source(con, origine=origine)
        _insert_source_document(con, source_id=src_id, path=origine)

        with patch.object(sut, "ROOT", self.tmp_path):
            sut._sync_deleted_files(con)

        rows = con.execute("SELECT id FROM source WHERE origine = ?", (origine,)).fetchall()
        self.assertEqual(rows, [], "La source dont le fichier n'existe plus doit être supprimée.")

    def test_mentions_orphelines_sont_nettoyees(self):
        """Les mentions liées à un document supprimé doivent être effacées."""
        con = _make_db()
        src_id = _insert_source(con, origine="sources/doc.pdf")
        ghost_path = "sources/ghost.md"
        doc_id = _insert_source_document(con, source_id=src_id, path=ghost_path)

        con.execute(
            "INSERT INTO named_entity (key, entity_type, display_name) VALUES (?, ?, ?)",
            ("jean_dupont", "person", "Jean Dupont"),
        )
        entity_id = con.execute(
            "SELECT id FROM named_entity WHERE key='jean_dupont'"
        ).fetchone()["id"]
        con.execute(
            "INSERT INTO mention (entity_id, source_document_id, source, page, extractor) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_id, doc_id, ghost_path, 1, "manual"),
        )
        con.commit()

        with patch.object(sut, "ROOT", self.tmp_path):
            sut._sync_deleted_files(con)

        remaining = con.execute(
            "SELECT id FROM mention WHERE source_document_id = ?", (doc_id,)
        ).fetchall()
        self.assertEqual(remaining, [], "Les mentions du document supprimé doivent être effacées.")


# ===========================================================================
# POINT 2 — Extraction PDF → Markdown (sections Page X)
# ===========================================================================


class TestNormalizeMdPageSections(_TmpDirMixin):
    """normalize_md_page_sections convertit les variantes d'en-tête vers ## Page X."""

    def test_convertit_entete_alternatif(self):
        md = _md(self.tmp_path, "doc.md", "# Page 1\n\nTexte de la page un.\n")
        self.assertTrue(sut.normalize_md_page_sections(md))
        self.assertIn("## Page 1", md.read_text(encoding="utf-8"))

    def test_ne_modifie_pas_entete_deja_normalise(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nContenu.\n")
        self.assertFalse(sut.normalize_md_page_sections(md))

    def test_retourne_false_si_fichier_absent(self):
        self.assertFalse(sut.normalize_md_page_sections(self.tmp_path / "absent.md"))


class TestEnsureSinglePageSection(_TmpDirMixin):
    """ensure_single_page_section ajoute ## Page 1 aux Markdown non paginés."""

    def test_ajoute_section_si_absente(self):
        md = _md(self.tmp_path, "doc.md", "Texte sans pagination.\n")
        self.assertTrue(sut.ensure_single_page_section(md))
        self.assertIn("## Page 1", md.read_text(encoding="utf-8"))

    def test_preserves_frontmatter(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\ntitre: Mon document\n---\n\nCorps du document.\n")
        sut.ensure_single_page_section(md)
        content = md.read_text(encoding="utf-8")
        self.assertLess(
            content.index("---"),
            content.index("## Page 1"),
            "Le front matter doit rester avant ## Page 1.",
        )

    def test_ne_modifie_pas_si_deja_pagine(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nContenu.\n")
        self.assertFalse(sut.ensure_single_page_section(md))

    def test_retourne_false_si_contenu_vide(self):
        md = _md(self.tmp_path, "empty.md", "   \n")
        self.assertFalse(sut.ensure_single_page_section(md))


class TestHasValidPageSections(_TmpDirMixin):
    """has_valid_page_sections vérifie la présence d'au moins une section ## Page X."""

    def test_valide_avec_sections(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nContenu.\n## Page 2\n\nSuite.\n")
        self.assertTrue(sut.has_valid_page_sections(md))

    def test_invalide_sans_section(self):
        md = _md(self.tmp_path, "doc.md", "Contenu sans pagination.\n")
        self.assertFalse(sut.has_valid_page_sections(md))

    def test_invalide_si_fichier_absent(self):
        self.assertFalse(sut.has_valid_page_sections(self.tmp_path / "absent.md"))


class TestParseMdPageSections(unittest.TestCase):
    """parse_md_page_sections extrait les sections de page et leur contenu."""

    def test_extrait_deux_sections(self):
        content = "## Page 1\n\nTexte A.\n## Page 2\n\nTexte B.\n"
        sections = sut.parse_md_page_sections(content)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0][0], "1")
        self.assertIn("Texte A", sections[0][1])
        self.assertEqual(sections[1][0], "2")
        self.assertIn("Texte B", sections[1][1])

    def test_retourne_liste_vide_si_pas_de_section(self):
        self.assertEqual(sut.parse_md_page_sections("Pas de sections."), [])

    def test_gere_plage_de_pages(self):
        sections = sut.parse_md_page_sections("## Page 3-4\n\nContenu.\n")
        self.assertEqual(sections[0][0], "3-4")


class TestMdStats(_TmpDirMixin):
    """md_stats retourne (nombre_pages, extrait, est_lisible)."""

    def test_fichier_absent_retourne_valeurs_negatives(self):
        pages, excerpt, readable = sut.md_stats(self.tmp_path / "absent.md")
        self.assertEqual(pages, -1)
        self.assertEqual(excerpt, "")
        self.assertFalse(readable)

    def test_compte_correctement_les_pages(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nA.\n## Page 2\n\nB.\n## Page 3\n\nC.\n")
        pages, _, _ = sut.md_stats(md)
        self.assertEqual(pages, 3)

    def test_detecte_contenu_lisible(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte informatif.\n")
        _, excerpt, readable = sut.md_stats(md)
        self.assertTrue(readable)
        self.assertGreater(len(excerpt), 0)


# ===========================================================================
# POINT 3 — Mise à jour BD avec les métadonnées extraites
# ===========================================================================


class TestNormalizeNumericDate(unittest.TestCase):
    def test_date_valide(self):
        self.assertEqual(sut.normalize_numeric_date("15", "3", "2020"), "2020-03-15")

    def test_date_invalide(self):
        self.assertEqual(sut.normalize_numeric_date("32", "13", "2020"), "0000-00-00")

    def test_zero_padding(self):
        self.assertEqual(sut.normalize_numeric_date("1", "1", "1900"), "1900-01-01")


class TestNormalizeNamedDate(unittest.TestCase):
    def test_mois_francais(self):
        self.assertEqual(sut.normalize_named_date("3", "mars", "1939"), "1939-03-03")

    def test_mois_allemand(self):
        self.assertEqual(sut.normalize_named_date("1", "Januar", "1920"), "1920-01-01")

    def test_mois_inconnu(self):
        self.assertEqual(sut.normalize_named_date("1", "xyzmonth", "2000"), "0000-00-00")

    def test_mois_avec_accent(self):
        self.assertEqual(sut.normalize_named_date("14", "février", "1918"), "1918-02-14")


class TestDetectDatePublicationFromMd(_TmpDirMixin):
    def test_date_numerique_explicite(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nDate de publication : 12/06/1936\n")
        self.assertEqual(sut.detect_date_publication_from_md(md), "1936-06-12")

    def test_date_publie_le(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nPublié le 03.09.1939.\n")
        self.assertEqual(sut.detect_date_publication_from_md(md), "1939-09-03")

    def test_retourne_zero_si_absent(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nAucune date ici.\n")
        self.assertEqual(sut.detect_date_publication_from_md(md), "0000-00-00")

    def test_retourne_zero_si_fichier_absent(self):
        self.assertEqual(
            sut.detect_date_publication_from_md(self.tmp_path / "absent.md"),
            "0000-00-00",
        )

    def test_date_nommee_francaise(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\n(du 4. avril 1938)\n")
        self.assertEqual(sut.detect_date_publication_from_md(md), "1938-04-04")


class TestIsProbableAuthorName(unittest.TestCase):
    def test_nom_simple_valide(self):
        self.assertTrue(sut.is_probable_author_name("Jean Dupont"))

    def test_nom_avec_particule(self):
        self.assertTrue(sut.is_probable_author_name("Charles de Gaulle"))

    def test_trop_court(self):
        self.assertFalse(sut.is_probable_author_name("AB"))

    def test_contient_url(self):
        self.assertFalse(sut.is_probable_author_name("http://example.com"))

    def test_contient_chiffres(self):
        self.assertFalse(sut.is_probable_author_name("Jean123 Dupont"))

    def test_trop_de_mots(self):
        self.assertFalse(sut.is_probable_author_name("Un Nom Avec Vraiment Trop De Mots"))

    def test_mot_cle_blackliste(self):
        self.assertFalse(sut.is_probable_author_name("Archives fédérales"))

    def test_nom_majuscules_ocr(self):
        # Formes OCR toutes-majuscules
        self.assertTrue(sut.is_probable_author_name("DUPONT"))


class TestDetectAuthorsFromMd(_TmpDirMixin):
    def test_extrait_auteur_via_label(self):
        # L'auteur doit être en fin de page : md_first_page_text aplatit les
        # sauts de ligne, donc le pattern [^|\n]+ capturerait tout le reste du
        # texte si des mots suivaient l'auteur sur la même « ligne aplatie ».
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nCorps du texte.\n\nAuteur : Jean Dupont\n")
        authors = sut.detect_authors_from_md(md, [])
        self.assertTrue(
            any("Dupont" in a or "Jean" in a for a in authors),
            f"Aucun auteur trouvé parmi : {authors}",
        )

    def test_retourne_auteur_connu_present_dans_texte(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nRédaction par Marie Curie pour le rapport.\n")
        authors = sut.detect_authors_from_md(md, ["Marie Curie"])
        self.assertIn("Marie Curie", authors)

    def test_retourne_liste_si_aucun_auteur(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nTexte quelconque sans auteur.\n")
        self.assertIsInstance(sut.detect_authors_from_md(md, []), list)


class TestNormalizeDoi(unittest.TestCase):
    def test_doi_url(self):
        self.assertEqual(
            sut.normalize_doi("https://doi.org/10.1234/test.2020"),
            "10.1234/test.2020",
        )

    def test_doi_brut(self):
        self.assertEqual(sut.normalize_doi("10.5678/example"), "10.5678/example")

    def test_chaine_vide(self):
        self.assertEqual(sut.normalize_doi(""), "")

    def test_sans_doi(self):
        self.assertEqual(sut.normalize_doi("pas un DOI"), "")

    def test_supprime_ponctuation_finale(self):
        self.assertFalse(sut.normalize_doi("10.1234/test.").endswith("."))


class TestNormalizeIsbn(unittest.TestCase):
    def test_isbn13_valide(self):
        self.assertEqual(sut.normalize_isbn("9780306406157"), "9780306406157")

    def test_isbn13_invalide(self):
        self.assertEqual(sut.normalize_isbn("9780306406158"), "")

    def test_isbn10_valide(self):
        self.assertEqual(sut.normalize_isbn("0306406152"), "0306406152")

    def test_chaine_vide(self):
        self.assertEqual(sut.normalize_isbn(""), "")

    def test_longueur_incorrecte(self):
        self.assertEqual(sut.normalize_isbn("12345"), "")


class TestNormalizeIssn(unittest.TestCase):
    def test_issn_valide(self):
        self.assertEqual(sut.normalize_issn("03785955"), "0378-5955")

    def test_issn_invalide(self):
        self.assertEqual(sut.normalize_issn("12345678"), "")

    def test_chaine_vide(self):
        self.assertEqual(sut.normalize_issn(""), "")

    def test_format_avec_tiret(self):
        self.assertEqual(sut.normalize_issn("0378-5955"), "0378-5955")


class TestCompactAuthorList(unittest.TestCase):
    def test_supprime_nom_de_famille_seul_si_forme_complete_presente(self):
        result = sut.compact_author_list(["Dupont", "Jean Dupont"])
        self.assertNotIn("Dupont", result)
        self.assertIn("Jean Dupont", result)

    def test_conserve_deux_auteurs_distincts(self):
        self.assertEqual(len(sut.compact_author_list(["Jean Dupont", "Marie Curie"])), 2)

    def test_liste_vide(self):
        self.assertEqual(sut.compact_author_list([]), [])

    def test_dedoublonne(self):
        result = sut.compact_author_list(["Jean Dupont", "Jean Dupont"])
        self.assertEqual(result.count("Jean Dupont"), 1)


class TestAssignIdentifiantSource(unittest.TestCase):
    def test_identifiant_unique_si_un_seul_element(self):
        entries = [{"identifiant_source_base": "SRC-TEST-2020", "signature": "aaa"}]
        sut.assign_identifiant_source(entries)
        self.assertEqual(entries[0]["identifiant_source"], "SRC-TEST-2020")

    def test_suffixe_numerique_si_collision(self):
        entries = [
            {"identifiant_source_base": "SRC-TEST-2020", "signature": "bbb"},
            {"identifiant_source_base": "SRC-TEST-2020", "signature": "aaa"},
        ]
        sut.assign_identifiant_source(entries)
        ids = {e["identifiant_source"] for e in entries}
        self.assertIn("SRC-TEST-2020", ids)
        self.assertIn("SRC-TEST-2020-02", ids)


class TestDetectCategorieFromMd(_TmpDirMixin):
    def test_document_officiel(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nMessage du Conseil fédéral du 3 mars 1939.\n")
        self.assertEqual(sut.detect_categorie_from_md(md, "titre"), "document officiel")

    def test_rapport(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nRapport d'étude sur la politique étrangère.\n")
        self.assertEqual(sut.detect_categorie_from_md(md, "rapport"), "rapport")

    def test_presse(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nRédaction du Journal de Genève.\n")
        self.assertEqual(sut.detect_categorie_from_md(md, "presse"), "presse")

    def test_autre_par_defaut(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte quelconque.\n")
        self.assertEqual(sut.detect_categorie_from_md(md, ""), "autre")


class TestDetectTypeSourceFromMd(_TmpDirMixin):
    def test_primaire_conseil_federal(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nMessage du Conseil fédéral aux Chambres.\n")
        result = sut.detect_type_source_from_md(md, "Message CF", "1939-03-01", "document officiel")
        self.assertEqual(result, "primaire")

    def test_secondaire_wikipedia(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nArticle Wikipedia sur la Suisse.\n")
        result = sut.detect_type_source_from_md(md, "Wikipedia", "2020-01-01", "autre")
        self.assertEqual(result, "secondaire")

    def test_secondaire_par_defaut(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nTexte neutre sans indicateur.\n")
        result = sut.detect_type_source_from_md(md, "", "0000-00-00", "autre")
        self.assertEqual(result, "secondaire")


class TestDetectPeriodesFromMd(_TmpDirMixin):
    def test_periode_explicite(self):
        md = _md(self.tmp_path, "doc.md",
                 "## Page 1\n\nLa période 1914-1918 fut difficile.\n")
        periodes = sut.detect_periodes_from_md(md, None)
        self.assertTrue(any("1914" in p for p in periodes))

    def test_retourne_liste_vide_si_fichier_absent(self):
        self.assertEqual(
            sut.detect_periodes_from_md(self.tmp_path / "absent.md", None), []
        )

    def test_utilise_fallback_si_pas_d_annees(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte sans aucune année.\n")
        fallback = ["1918-1939"]
        self.assertEqual(sut.detect_periodes_from_md(md, fallback), fallback)


class TestBuildResumeFromMd(_TmpDirMixin):
    def test_extrait_phrase_informative(self):
        md = _md(
            self.tmp_path, "doc.md",
            "## Page 1\n\nLa Confédération helvétique a adopté une politique de neutralité armée. "
            "Cette décision fut prise lors de la Diète de 1815.\n",
        )
        resume = sut.build_resume_from_md(md)
        self.assertGreaterEqual(len(resume), 40)
        self.assertTrue(
            any(w in resume for w in ["Confédération", "neutralité", "décision", "1815"])
        )

    def test_retourne_chaine_vide_si_absent(self):
        self.assertEqual(sut.build_resume_from_md(self.tmp_path / "absent.md"), "")

    def test_ignore_bruits_interface(self):
        md = _md(
            self.tmp_path, "doc.md",
            "## Page 1\n\naccueil contact cookies\n\n"
            "La guerre de 1914-1918 bouleversa les équilibres européens et suisses.\n",
        )
        resume = sut.build_resume_from_md(md)
        self.assertNotIn("accueil", resume.lower())
        self.assertNotIn("contact", resume.lower())


# ===========================================================================
# POINT 4 — Recherche d'entités nommées (NER)
# ===========================================================================


class TestFrontmatterFrenchRatio(_TmpDirMixin):
    """_frontmatter_french_ratio calcule le ratio de français depuis le front matter."""

    def test_language_fr_retourne_1(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage: fr\n---\n\n## Page 1\n\nTexte.\n")
        self.assertEqual(sut._frontmatter_french_ratio(md), 1.0)

    def test_language_de_retourne_0(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage: de\n---\n\n## Page 1\n\nText.\n")
        self.assertEqual(sut._frontmatter_french_ratio(md), 0.0)

    def test_distribution_fr_majoritaire(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage_distribution: fr:95, de:5\n---\n\n## Page 1\n\nTexte.\n")
        self.assertGreater(sut._frontmatter_french_ratio(md), 0.9)

    def test_sans_information_de_langue(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\ntitre: Mon doc\n---\n\n## Page 1\n\nTexte.\n")
        self.assertEqual(sut._frontmatter_french_ratio(md), 0.0)

    def test_fichier_absent(self):
        self.assertEqual(sut._frontmatter_french_ratio(self.tmp_path / "absent.md"), 0.0)


class TestIsMostlyFrenchMarkdown(_TmpDirMixin):
    """>90 % de français → True."""

    def test_vrai_si_fr_dominant(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage_distribution: fr:98, de:2\n---\n\n## Page 1\n\nTexte.\n")
        self.assertTrue(sut.is_mostly_french_markdown(md))

    def test_faux_si_non_francais(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage: de\n---\n\n## Page 1\n\nText.\n")
        self.assertFalse(sut.is_mostly_french_markdown(md))


class TestEffectiveFrenchRatio(_TmpDirMixin):
    """_effective_french_ratio retourne 1.0 par défaut (absence d'info = 100 % FR)."""

    def test_sans_info_langue_retourne_1(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\ntitre: Sans langue\n---\n\n## Page 1\n\nTexte.\n")
        self.assertEqual(sut._effective_french_ratio(md), 1.0)

    def test_fichier_non_md_retourne_0(self):
        pdf = self.tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        self.assertEqual(sut._effective_french_ratio(pdf), 0.0)

    def test_language_fr_retourne_1(self):
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage: fr\n---\n\n## Page 1\n\nTexte.\n")
        self.assertEqual(sut._effective_french_ratio(md), 1.0)


class TestChooseFrenchMarkdownForNer(_TmpDirMixin):
    """choose_french_markdown_for_ner sélectionne le Markdown le plus français."""

    def test_retourne_none_si_liste_vide(self):
        self.assertIsNone(sut.choose_french_markdown_for_ner([]))

    def test_prefere_fr_sur_de(self):
        fr_md = _md(self.tmp_path, "doc_fr.md",
                    "---\nlanguage: fr\n---\n\n## Page 1\n\nTexte.\n")
        de_md = _md(self.tmp_path, "doc_de.md",
                    "---\nlanguage: de\n---\n\n## Page 1\n\nText.\n")
        self.assertEqual(sut.choose_french_markdown_for_ner([de_md, fr_md]), fr_md)

    def test_ignore_fichiers_non_md(self):
        pdf = self.tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")
        md = _md(self.tmp_path, "doc.md",
                 "---\nlanguage: fr\n---\n\n## Page 1\n\nTexte.\n")
        self.assertEqual(sut.choose_french_markdown_for_ner([pdf, md]), md)

    def test_retourne_none_si_aucun_md(self):
        pdf = self.tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")
        self.assertIsNone(sut.choose_french_markdown_for_ner([pdf]))

    def test_md_sans_info_langue_eligible(self):
        """Un Markdown sans front matter de langue est supposé 100 % FR et donc éligible."""
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte en français.\n")
        self.assertEqual(sut.choose_french_markdown_for_ner([md]), md)


class TestRunNamedEntitiesExtraction(_TmpDirMixin):
    """run_named_entities_extraction retourne False si le module NER est absent."""

    def test_retourne_false_si_module_ner_absent(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nJean Dupont fut colonel.\n")
        with patch.object(sut, "_load_ner_module", return_value=None):
            self.assertFalse(sut.run_named_entities_extraction(md, quiet=True))

    def test_retourne_false_si_api_manquante(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte.\n")
        with patch.object(sut, "_load_ner_module", return_value=MagicMock(spec=[])):
            self.assertFalse(sut.run_named_entities_extraction(md, quiet=True))

    def test_retourne_true_si_ner_reussit(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte.\n")
        fake_ner = MagicMock()
        fake_ner.extract_entities_to_db.return_value = {"action": "inserted"}
        with patch.object(sut, "_load_ner_module", return_value=fake_ner):
            self.assertTrue(sut.run_named_entities_extraction(md, quiet=True))

    def test_retourne_true_si_ner_skipped(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte.\n")
        fake_ner = MagicMock()
        fake_ner.extract_entities_to_db.return_value = {"action": "skipped"}
        with patch.object(sut, "_load_ner_module", return_value=fake_ner):
            self.assertTrue(sut.run_named_entities_extraction(md, quiet=True))

    def test_retourne_false_si_exception_ner(self):
        md = _md(self.tmp_path, "doc.md", "## Page 1\n\nTexte.\n")
        fake_ner = MagicMock()
        fake_ner.extract_entities_to_db.side_effect = RuntimeError("échec spacy")
        # to_rel() lèverait ValueError si md_path est hors de ROOT : on le patche.
        with patch.object(sut, "_load_ner_module", return_value=fake_ner):
            with patch.object(sut, "to_rel", return_value="sources/doc.md"):
                self.assertFalse(sut.run_named_entities_extraction(md, quiet=True))


if __name__ == "__main__":
    unittest.main()



