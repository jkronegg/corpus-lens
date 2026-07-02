#!/usr/bin/env python3
"""Convertisseur HTML -> Markdown pour les notices DHS (hls-dhs-dss.ch).

Extrait le contenu du div#xwikicontent et produit un Markdown propre.

Usage:
    python dhs_html_to_md.py <fichier.html>               # stdout
    python dhs_html_to_md.py <fichier.html> -o out.md     # fichier
    python dhs_html_to_md.py --batch sources_en_ligne/dhs/html_cache/
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

DHS_BASE = "https://hls-dhs-dss.ch"
SKILL_NAME = "fetch-dhs-article"
TRACKING_HOST_MARKERS = (
    "crwdcntrl.net",
    "scorecardresearch.com",
    "doubleclick.net",
    "googletagmanager.com",
    "google-analytics.com",
)

# Tags a ignorer completement (contenu + balises)
SKIP_TAGS = {
    "script", "style", "nav", "footer", "header",
    "button", "form", "input", "select", "textarea",
}
# Classes DIV a ignorer
SKIP_DIV_CLASSES = {
    "hls-service-box",        # liens/index thematique
    "hls-language-selector",  # selecteur de langue
    "hls-share-container",    # boutons de partage
    "social-media-icons-container",
    "hls-service-box-right",
    "hls-service-box-left",
    "hls-article-service-box",
    "hls-footer",             # cartouche footer avec liens
    "footer",                 # footer generique
    "feedback",               # bouton de feedback
    "hls-feedback",           # feedback DHS specifique
}
# Sous-elements de contenu a ignorer (selon classe CSS)
SKIP_CONTENT_CLASSES = {
    "hls-media-legend-more",  # suffixe tronque "[…]" dans les legendes
}
# Tags dont on garde seulement le contenu (on supprime la balise)
INLINE_PASSTHROUGH = {"span", "div", "section", "article", "main", "aside", "figure"}
# Tags de bloc qui genèrent une ligne vide avant/apres
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote"}


class DhsHtmlParser(HTMLParser):
    """Parser HTML a passage unique qui produit du Markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: List[str] = []           # pile des tags ouverts
        self._skip_depth: int = 0             # profondeur dans un tag a ignorer
        self._parts: List[str] = []           # fragments de texte/md accumulés
        self._in_li: bool = False
        self._li_depth: int = 0
        self._in_heading: Optional[str] = None
        self._heading_text: str = ""
        self._in_em: bool = False
        self._in_strong: bool = False
        self._in_sup: bool = False
        self._in_link: bool = False
        self._link_href: str = ""
        self._link_text: str = ""
        self._in_xwikicontent: bool = False
        self._xwiki_depth: int = 0            # pour savoir quand on sort du div
        self._in_img_legend: bool = False
        self._legend_text: str = ""
        self._skip_div_depth: int = 0         # pour ignorer des DIV par classe
        self._skip_class_depth: int = 0       # pour ignorer des sous-elements par classe CSS

        # Etat de conversion des tableaux HTML -> table Markdown
        self._in_table: bool = False
        self._table_rows: List[List[str]] = []
        self._table_row_has_header_flags: List[bool] = []
        self._current_row: List[str] = []
        self._current_row_has_header: bool = False
        self._current_cell_parts: List[str] = []
        self._in_cell: bool = False
        self._current_cell_is_header: bool = False

        # Metadonnées collectées
        self.meta: dict = {
            "titre": "",
            "auteur": "",
            "traduction": "",
            "version": "",
            "citation": "",
            "url_canonique": "",
            "language_distribution":"",
        }
        self._collecting_meta: str = ""       # quel champ meta on collecte

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _attr(self, attrs: list, name: str) -> str:
        for k, v in attrs:
            if k == name:
                return v or ""
        return ""

    def _has_class(self, attrs: list, *classes: str) -> bool:
        cls = self._attr(attrs, "class")
        return any(c in cls for c in classes)

    def _has_id(self, attrs: list, id_: str) -> bool:
        return self._attr(attrs, "id") == id_

    def _push(self, text: str) -> None:
        if self._in_xwikicontent and self._skip_depth == 0 and self._skip_div_depth == 0:
            self._parts.append(text)

    def _resolve_href(self, href: str) -> str:
        if href.startswith("/"):
            return DHS_BASE + href
        return href

    def _append_output(self, text: str) -> None:
        """Ecrit soit dans la cellule de tableau courante, soit dans le flux Markdown global."""
        if self._in_table and self._in_cell:
            self._current_cell_parts.append(text)
            return
        self._push(text)

    def _normalize_table_cell(self, raw: str) -> str:
        text = re.sub(r"\s+", " ", (raw or "")).strip()
        # Echappement minimal pour GFM
        text = text.replace("|", r"\|")
        return text

    def _flush_current_cell(self) -> None:
        if not self._in_table or not self._in_cell:
            return
        cell_text = self._normalize_table_cell("".join(self._current_cell_parts))
        self._current_row.append(cell_text)
        if self._current_cell_is_header:
            self._current_row_has_header = True
        self._current_cell_parts = []
        self._in_cell = False
        self._current_cell_is_header = False

    def _flush_current_row(self) -> None:
        if not self._in_table:
            return
        self._flush_current_cell()
        if not self._current_row:
            return
        self._table_rows.append(self._current_row)
        self._table_row_has_header_flags.append(self._current_row_has_header)
        self._current_row = []
        self._current_row_has_header = False

    def _emit_markdown_table(self) -> None:
        rows = [row for row in self._table_rows if any(cell.strip() for cell in row)]
        if not rows:
            return

        header_index = 0
        for idx, has_header in enumerate(self._table_row_has_header_flags):
            if has_header and idx < len(rows):
                header_index = idx
                break

        max_cols = max(len(row) for row in rows)
        normalized_rows: List[List[str]] = [row + [""] * (max_cols - len(row)) for row in rows]

        header_row = normalized_rows[header_index]
        data_rows = [row for idx, row in enumerate(normalized_rows) if idx != header_index]

        lines = [
            "| " + " | ".join(header_row) + " |",
            "| " + " | ".join(["---"] * max_cols) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in data_rows)

        self._push("\n" + "\n".join(lines) + "\n")

    # ------------------------------------------------------------------
    # HTMLParser interface
    # ------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._stack.append(tag)

        # --- Detection du div#xwikicontent ---
        if tag == "div" and self._has_id(attrs, "xwikicontent"):
            self._in_xwikicontent = True
            self._xwiki_depth = len(self._stack)
            return

        if not self._in_xwikicontent:
            # On recupere quand meme le canonical hors du div
            if tag == "link" and self._attr(attrs, "rel") == "canonical":
                self.meta["url_canonique"] = self._attr(attrs, "href")
            return

        # --- Tags DIV a ignorer par classe ---
        if tag == "div" and self._skip_div_depth == 0:
            cls = self._attr(attrs, "class")
            if any(c in cls for c in SKIP_DIV_CLASSES):
                self._skip_div_depth += 1
                return

        if self._skip_div_depth > 0:
            if tag == "div":
                self._skip_div_depth += 1
            return

        # --- Sous-elements a ignorer par classe (pas uniquement des div) ---
        if self._skip_class_depth == 0:
            cls = self._attr(attrs, "class")
            if any(c in cls for c in SKIP_CONTENT_CLASSES):
                self._skip_class_depth = 1
                return
        elif self._skip_class_depth > 0:
            self._skip_class_depth += 1
            return

        # --- Tags a ignorer ---
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        # --- Tableaux HTML -> Markdown ---
        if tag == "table":
            self._in_table = True
            self._table_rows = []
            self._table_row_has_header_flags = []
            self._current_row = []
            self._current_row_has_header = False
            self._current_cell_parts = []
            self._in_cell = False
            self._current_cell_is_header = False
            return

        if self._in_table:
            if tag == "tr":
                self._flush_current_row()
                self._current_row = []
                self._current_row_has_header = False
                return
            if tag in {"th", "td"}:
                self._flush_current_cell()
                self._in_cell = True
                self._current_cell_is_header = tag == "th"
                self._current_cell_parts = []
                return
            if tag == "br" and self._in_cell:
                self._current_cell_parts.append(" <br> ")
                return

        # --- Titre H1 ---
        if tag == "h1":
            self._in_heading = "#"
            self._heading_text = ""
            return

        if tag == "h2":
            self._in_heading = "##"
            self._heading_text = ""
            return

        if tag == "h3":
            self._in_heading = "###"
            self._heading_text = ""
            return

        if tag == "h4":
            self._in_heading = "####"
            self._heading_text = ""
            return

        # --- Liens ---
        if tag == "a":
            href = self._attr(attrs, "href")
            if href and not href.startswith("#") and not href.startswith("javascript"):
                self._in_link = True
                self._link_href = self._resolve_href(href)
                self._link_text = ""
            return

        # --- Emphase ---
        if tag in ("em", "i"):
            self._in_em = True
            return

        if tag in ("strong", "b"):
            self._in_strong = True
            return

        if tag == "sup":
            self._in_sup = True
            return

        # --- Listes ---
        if tag == "li":
            self._in_li = True
            self._push("\n")
            indent = "  " * max(0, self._li_depth - 1)
            self._push(indent + "- ")
            return

        if tag == "ul":
            self._li_depth += 1
            self._push("\n")
            return

        if tag == "ol":
            self._li_depth += 1
            self._push("\n")
            return

        # --- Images ---
        if tag == "img":
            src = self._attr(attrs, "src")
            alt = self._attr(attrs, "alt")
            if src:
                full_src = self._resolve_href(src.split("?")[0])
                self._push(f"\n![{alt}]({full_src})\n")
            return

        # --- Legendes media ---
        if tag == "div" and self._has_class(attrs, "hls-media-legend"):
            self._in_img_legend = True
            self._legend_text = ""
            return

        # --- Auteur ---
        if tag == "div" and self._has_class(attrs, "hls-article-text-author"):
            self._collecting_meta = "auteur_block"
            self._push("\n")
            return

        # --- Citation ---
        if tag == "div" and self._has_class(attrs, "hls-citation-suggestion"):
            self._collecting_meta = "citation"
            self._push("\n---\n\n**Suggestion de citation**\n\n")
            return

        # --- Blocs generiques -> saut de ligne ---
        if tag in BLOCK_TAGS:
            self._push("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

        if not self._in_xwikicontent:
            return

        # --- Fin des DIV a ignorer par classe ---
        if self._skip_div_depth > 0:
            if tag == "div":
                self._skip_div_depth -= 1
            return

        # --- Fin des sous-elements ignores par classe ---
        if self._skip_class_depth > 0:
            self._skip_class_depth -= 1
            return

        # --- Fin du skip (SKIP_TAGS) ---
        if tag in SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return

        if self._skip_depth > 0:
            return

        # --- Titres ---
        if tag in ("h1", "h2", "h3", "h4") and self._in_heading:
            level = self._in_heading
            title = self._heading_text.strip()
            if tag == "h1":
                self.meta["titre"] = title
            self._push(f"\n{level} {title}\n\n")
            self._in_heading = None
            self._heading_text = ""
            return

        # --- Liens ---
        if tag == "a" and self._in_link:
            text = self._link_text.strip()
            href = self._link_href
            if text:
                self._append_output(f"[{text}]({href})")
            self._in_link = False
            self._link_href = ""
            self._link_text = ""
            return

        # --- Tableaux HTML -> Markdown ---
        if self._in_table:
            if tag in {"th", "td"}:
                self._flush_current_cell()
                return
            if tag == "tr":
                self._flush_current_row()
                return
            if tag == "table":
                self._flush_current_row()
                self._emit_markdown_table()
                self._in_table = False
                self._table_rows = []
                self._table_row_has_header_flags = []
                self._current_row = []
                self._current_row_has_header = False
                self._current_cell_parts = []
                self._in_cell = False
                self._current_cell_is_header = False
                return

        # --- Emphase ---
        if tag in ("em", "i"):
            self._in_em = False
            return

        if tag in ("strong", "b"):
            self._in_strong = False
            return

        if tag == "sup":
            self._in_sup = False
            return

        # --- Listes ---
        if tag == "li":
            self._in_li = False
            self._push("\n")
            return

        if tag in ("ul", "ol"):
            self._li_depth = max(0, self._li_depth - 1)
            self._push("\n")
            return

        # --- Legendes ---
        if tag == "div" and self._in_img_legend:
            self._push(f"*{self._legend_text.strip()}*\n\n")
            self._in_img_legend = False
            self._legend_text = ""
            return

        # --- Blocs generiques -> saut de ligne ---
        if tag in BLOCK_TAGS:
            self._push("\n")

        # --- Fin du xwikicontent ---
        if tag == "div" and self._in_xwikicontent and len(self._stack) < self._xwiki_depth:
            self._in_xwikicontent = False

    def handle_data(self, data: str) -> None:
        if (
            not self._in_xwikicontent
            or self._skip_depth > 0
            or self._skip_div_depth > 0
            or self._skip_class_depth > 0
        ):
            return

        text = data  # convert_charrefs=True gere deja les entites

        # Dans un heading
        if self._in_heading is not None:
            self._heading_text += text
            return

        # Dans une legende image
        if self._in_img_legend:
            self._legend_text += text
            return

        # Dans un tableau, on ne garde le texte que dans les cellules
        if self._in_table and not self._in_cell:
            return

        # Applique les decorations inline
        if self._in_link:
            self._link_text += text
            return

        if self._in_strong:
            text = f"**{text}**" if text.strip() else text
        elif self._in_em:
            text = f"*{text}*" if text.strip() else text

        if self._in_sup and text.strip():
            text = f"^{text.strip()}^"

        self._append_output(text)


# ------------------------------------------------------------------
# Post-traitement du Markdown brut
# ------------------------------------------------------------------

def post_process(raw: str) -> str:
    lines = [l.rstrip() for l in raw.splitlines()]
    # Supprime les espaces de debut de ligne (indentations parasites)
    lines = [l.lstrip() if not l.startswith("- ") and not l.startswith("  ") else l for l in lines]
    # Supprime le H3 "Suggestion de citation" duplique (on le remplace par le separateur du block)
    lines = [l for l in lines if l.strip() != "### Suggestion de citation"]
    
    # Supprime le footer et feedback apres le bloc de citation
    # On cherche la fin du bloc "consulté le" et on coupe tout apres
    cutoff_idx = None
    for i, line in enumerate(lines):
        if "consulté le" in line:
            cutoff_idx = i + 1
            # Cherche le prochain blank line apres et coupe apres celui-ci
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "":
                    cutoff_idx = j
                    break
            break
    if cutoff_idx is not None:
        lines = lines[:cutoff_idx]
    
    # Reduit les blocs de plus de 1 ligne vide consecutive
    result: List[str] = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count <= 1:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)
    return "\n".join(result).strip() + "\n"


def _clean_citation_text(value: str) -> str:
    """Supprime les en-tetes editoriaux de la citation avant front matter."""
    text = (value or "").strip()
    text = re.sub(r"(?is)^\s*#{1,6}\s*suggestion\s+de\s+citation\s*", "", text)
    text = re.sub(r"(?is)^\s*\*{1,2}\s*suggestion\s+de\s+citation\s*\*{1,2}\s*", "", text)
    text = re.sub(r"(?is)^\s*suggestion\s+de\s+citation\s*[:\-]?\s*", "", text)
    return " ".join(text.split())


class FrontMatter:
    """Gère la génération du front matter YAML pour les articles DHS."""
    
    FIELD_ORDER = [
        "titre",
        "auteur",
        "traduction",
        "version",
        "url",
        "citation",
        "author",
        "language_distribution",
    ]
    
    def __init__(self, meta: dict) -> None:
        """Initialise avec les métadonnées extraites du HTML."""
        language_distribution = (meta.get("language_distribution") or "").strip() or "fr:100"
        self.meta = {
            "titre": meta.get("titre", ""),
            "auteur": meta.get("auteur", ""),
            "traduction": meta.get("traduction", ""),
            "version": meta.get("version", ""),
            "url": meta.get("url_canonique", ""),
            "citation": meta.get("citation", ""),
            "transformation_by": meta.get("transformation_by", "skill " + SKILL_NAME),
            "language_distribution": language_distribution,
        }
    
    @staticmethod
    def _escape_yaml_value(value: str) -> str:
        """Échappe les valeurs YAML pour éviter les conflits."""
        if not value:
            return '""'
        # Remplace les " par '
        escaped = value.replace('"', "'")
        return f'"{escaped}"'
    
    def build(self) -> str:
        """Génère le front matter YAML formaté."""
        lines = ["---"]
        
        for field in self.FIELD_ORDER:
            value = self.meta.get(field, "")
            if value and value.strip():
                escaped = self._escape_yaml_value(value)
                lines.append(f"{field}: {escaped}")
        
        lines.append("---\n")
        return "\n".join(lines)


def build_frontmatter(meta: dict) -> str:
    """Génère le front matter YAML pour les métadonnées de l'article."""
    fm = FrontMatter(meta)
    return fm.build()


# ------------------------------------------------------------------
# Extraction auteur/version depuis le texte brut généré
# ------------------------------------------------------------------

def extract_meta_from_text(md: str, meta: dict) -> str:
    """Extrait auteur/version du texte et les retire du corps."""
    # Auteur: "Autrice/Auteur: Prenom Nom\nTraduction:\nPrenom Nom"
    # Le bloc texte-auteur genere: "Autrice/Auteur:\nPrenom Nom\nTraduction:\nPrenom Nom"
    m = re.search(
        r"Autrice/Auteur[:\s]*\n([\s\S]*?)(?=\n\n|\Z)",
        md,
    )
    if m:
        block = m.group(0)
        # Extrait auteur
        a = re.search(r"Autrice/Auteur[:\s]*\n([^\n]+)", block)
        if a:
            meta["auteur"] = a.group(1).strip()
        # Extrait traduction
        t = re.search(r"Traduction[:\s]*\n([^\n]+)", block)
        if t:
            meta["traduction"] = t.group(1).strip()
        md = md.replace(block, "")
    else:
        # Variante compacte "Autrice/Auteur: Nom Traduction: Nom"
        m2 = re.search(r"Autrice/Auteur:\s*(.+?)(?:\s+Traduction:\s*(.+?))?(?:\n|$)", md)
        if m2:
            meta["auteur"] = m2.group(1).strip()
            if m2.group(2):
                meta["traduction"] = m2.group(2).strip()
            md = md.replace(m2.group(0), "")

    # Traduction seule sur une ligne residuelle
    m3 = re.search(r"\nTraduction:\s*\n([^\n]+)\n", md)
    if m3 and not meta.get("traduction"):
        meta["traduction"] = m3.group(1).strip()
        md = md.replace(m3.group(0), "\n")

    # Version
    m4 = re.search(r"Version de\s+(.+?)(?:\n|$)", md)
    if m4:
        meta["version"] = m4.group(1).strip()

    # Citation : cherche le bloc complet après "Suggestion de citation"
    marker = re.search(r"\*\*Suggestion de citation\*\*", md, re.IGNORECASE)
    if marker:
        tail = md[marker.end():]
        # Cherche un bloc de texte qui contient "consulté le" sur plusieurs lignes
        # On prend tout depuis le début jusqu'à la ligne contenant "consulté le"
        m5 = re.search(
            r"([^\n]*?consulté le[^\n]*)",
            tail,
            re.IGNORECASE | re.DOTALL,
        )
        if m5:
            # Récupère le texte complet, en commençant par le premier caractère non-whitespace
            citation_text = m5.group(1).strip()
            # Cherche s'il y a des lignes avant qui font partie de la citation
            before_citation = tail[: m5.start()].rstrip()
            if before_citation:
                # Prend les dernières lignes du texte avant "consulté le" comme début
                lines_before = before_citation.split('\n')
                # Trouve la première ligne qui contient du texte de citation (pas juste whitespace)
                for i in range(len(lines_before) - 1, -1, -1):
                    line = lines_before[i].strip()
                    if line and not line.startswith("-"):
                        # Reconstruit la citation complète
                        citation_text = " ".join(lines_before[i:] + [citation_text]).strip()
                        break
            meta["citation"] = _clean_citation_text(citation_text)

    # Fallback citation : cherche directement le pattern complet
    if not meta.get("citation"):
        m5 = re.search(
            r"((?:[A-Z][a-zù]+\s+)+[A-Z][a-zù]+:.*?consulté le[^\n.]*\.?)",
            md,
            re.IGNORECASE | re.DOTALL,
        )
        if m5:
            meta["citation"] = _clean_citation_text(m5.group(1))

    return md


def _safe_image_filename(url: str, index: int) -> str:
    """Construit un nom de fichier local deterministe pour une image distante."""
    parsed = urlsplit(url)
    raw_name = Path(unquote(parsed.path)).name
    stem = Path(raw_name).stem if raw_name else f"image_{index:03d}"
    suffix = Path(raw_name).suffix.lower() if raw_name else ""

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or f"image_{index:03d}"
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".tif", ".tiff", ".bmp", ".avif"}:
        suffix = ".jpg"

    return f"{index:03d}_{stem}{suffix}"


def _is_probable_content_image(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.netloc or "").lower()
    if any(marker in host for marker in TRACKING_HOST_MARKERS):
        return False

    path = (parsed.path or "").lower()
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp", ".tif", ".tiff")):
        return True

    return "/download/articles/" in path


def download_and_rewrite_images(
    md: str,
    md_out_path: Path,
    images_dir: Optional[Path],
    browser_image_downloader: Optional[Callable[[str, Path], bool]] = None,
) -> Tuple[str, int, int]:
    """Telecharge les images distantes et reecrit les liens Markdown en chemins locaux."""
    pattern = re.compile(r"!\[([^]]*)]\((https?://[^)\s]+)\)")
    matches = list(pattern.finditer(md))
    if not matches:
        return md, 0, 0

    # Si un dossier est fourni, on cree un sous-dossier par fichier pour eviter les collisions en batch.
    target_dir = (images_dir / md_out_path.stem) if images_dir else (md_out_path.parent / f"{md_out_path.stem}_images")
    target_dir.mkdir(parents=True, exist_ok=True)

    url_to_local: dict = {}
    downloaded = 0
    failed = 0

    unique_urls: List[str] = []
    seen = set()
    for m in matches:
        url = m.group(2)
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    for index, url in enumerate(unique_urls, start=1):
        if not _is_probable_content_image(url):
            failed += 1
            print(f"[warn] Image ignoree (tracking/non-image): {url}", file=sys.stderr)
            continue

        filename = _safe_image_filename(url, index)
        out_img = target_dir / filename
        try:
            if not out_img.exists():
                if browser_image_downloader is not None:
                    ok = browser_image_downloader(url, out_img)
                    if not ok:
                        raise RuntimeError("telechargement image via navigateur CDP impossible")
                else:
                    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (dhs_html_to_md)"})
                    with urlopen(req, timeout=20) as response:
                        out_img.write_bytes(response.read())
                downloaded += 1

            rel_path = str(out_img.relative_to(md_out_path.parent)).replace("\\", "/")
            url_to_local[url] = rel_path
        except Exception as exc:
            failed += 1
            print(f"[warn] Image non telechargee: {url} ({exc})", file=sys.stderr)

    def _replace(m: re.Match) -> str:
        alt, url = m.group(1), m.group(2)
        local = url_to_local.get(url)
        if not local:
            return m.group(0)
        return f"![{alt}]({local})"

    return pattern.sub(_replace, md), downloaded, failed


# ------------------------------------------------------------------
# Fonction principale de conversion
# ------------------------------------------------------------------

def convert_dhs_html_to_md(html_content: str) -> Tuple[str, dict]:
    """Convertit le HTML DHS en Markdown. Retourne (markdown, meta)."""
    parser = DhsHtmlParser()
    parser.feed(html_content)

    raw_md = "".join(parser.parts if hasattr(parser, "parts") else parser._parts)
    meta = parser.meta

    raw_md = extract_meta_from_text(raw_md, meta)
    frontmatter = build_frontmatter(meta)
    body = post_process(raw_md)
    return frontmatter + body, meta


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def convert_file(
    html_path: Path,
    out_path: Optional[Path],
    download_images: bool = False,
    images_dir: Optional[Path] = None,
) -> None:
    content = html_path.read_text(encoding="utf-8", errors="ignore")
    md, meta = convert_dhs_html_to_md(content)

    img_downloaded = 0
    img_failed = 0

    if download_images:
        if out_path is None:
            print("[warn] --download-images ignore sans --output (mode stdout).", file=sys.stderr)
        else:
            md, img_downloaded, img_failed = download_and_rewrite_images(md, out_path, images_dir)

    if out_path:
        out_path.write_text(md, encoding="utf-8")
        if download_images:
            print(
                f"  -> {out_path}  (titre: {meta.get('titre', '?')}, images: +{img_downloaded}/-{img_failed})"
            )
        else:
            print(f"  -> {out_path}  (titre: {meta.get('titre', '?')})")
    else:
        print(md)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Convertit un HTML DHS en Markdown")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("html_file", nargs="?", type=Path, help="Fichier HTML a convertir")
    group.add_argument("--batch", type=Path, help="Dossier contenant des *.html a convertir en masse")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Fichier .md de sortie (mode fichier unique)")
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Telecharge les images distantes et reecrit les liens Markdown en local",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Dossier racine des images (defaut: <fichier>_images a cote du markdown)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Dossier de sortie pour le mode batch (defaut: meme dossier que les HTML)"
    )
    args = parser.parse_args(argv)

    if args.batch:
        html_files = sorted(args.batch.glob("*.html"))
        if not html_files:
            print(f"Aucun fichier .html trouve dans {args.batch}", file=sys.stderr)
            return 1
        out_dir = args.out_dir or args.batch
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in html_files:
            out = out_dir / f.with_suffix(".md").name
            convert_file(f, out, download_images=args.download_images, images_dir=args.images_dir)
        print(f"\n{len(html_files)} fichier(s) convertis dans {out_dir}")
        return 0

    if args.html_file:
        convert_file(
            args.html_file,
            args.output,
            download_images=args.download_images,
            images_dir=args.images_dir,
        )
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))





