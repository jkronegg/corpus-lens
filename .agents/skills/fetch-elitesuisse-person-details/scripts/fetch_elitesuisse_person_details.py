#!/usr/bin/env python3
"""Recherche une personne dans l'index EliteSuisses puis exporte sa fiche en Markdown.

Flux:
1) chercher la personne dans le CSV d'index (asset du skill)
2) si absente: l'indiquer explicitement
3) si trouvée: ouvrir l'URL de la fiche via Playwright (CDP) et extraire les sections
4) écrire un fichier Markdown dans sources/elitesuisses/ avec front matter YAML
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlsplit
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

SKILL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[4]
DB_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
_DB_MODULE_PATH = DB_SCRIPTS_DIR / "db.py"
_DETECT_LANG_PATH = REPO_ROOT / ".agents" / "skills" / "translate-markdown" / "scripts" / "detect_markdown_language.py"
get_db_connection = None
register_source_document = None
try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_elitesuisse", _DB_MODULE_PATH)
    if spec and spec.loader:
        _db_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _db_module
        spec.loader.exec_module(_db_module)
        get_db_connection = _db_module.get_connection
        register_source_document = _db_module.register_source_document
        DB_AVAILABLE = True
    else:
        DB_AVAILABLE = False
except Exception:
    DB_AVAILABLE = False


def _load_language_detection_functions():
    if not _DETECT_LANG_PATH.exists():
        return None, None

    module_name = "detect_markdown_language_shared_for_elitesuisse"
    spec = importlib.util.spec_from_file_location(module_name, _DETECT_LANG_PATH)
    if spec is None or spec.loader is None:
        return None, None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "detect_language_distribution", None), getattr(module, "format_distribution", None)


_detect_language_distribution, _format_distribution = _load_language_detection_functions()

DEFAULT_CSV = SKILL_ROOT / "assets" / "elitessuisses_personnes_A_Z.csv"
DEFAULT_OUT_DIR = Path("sources/elitesuisses")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
EXCLUDED_IMAGE_FILENAMES = {
    "logo_snf.png",
    "logo_obelis.png",
    "logo_cdh.png",
    "favicon.png",
}
TRACKING_HOST_MARKERS = (
    "crwdcntrl.net",
    "scorecardresearch.com",
    "doubleclick.net",
    "googletagmanager.com",
    "google-analytics.com",
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def _slugify(text: str) -> str:
    text = _normalize(text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "personne"


def _yaml_quote(text: str) -> str:
    return (text or "").replace('"', "'")


def _compute_language_distribution(text: str) -> str:
    if callable(_detect_language_distribution) and callable(_format_distribution):
        detected = _detect_language_distribution(text)
        return _format_distribution(detected)
    return "unknown:100"


def _extract_person_id(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    ids = qs.get("id", [])
    raw = ids[0] if ids else ""
    raw = re.sub(r"[^0-9A-Za-z_-]", "", raw)
    return raw or "inconnu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch des détails EliteSuisses d'une personne depuis l'index CSV"
    )
    parser.add_argument("--name", required=True, help="Nom recherché (ex: 'Albert Aa, von der')")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV,
        help="Chemin du CSV d'index EliteSuisses",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Dossier de sortie Markdown (défaut: sources/elitesuisses)",
    )
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Endpoint CDP")
    parser.add_argument(
        "--candidate-index",
        type=int,
        default=1,
        help="Index 1-based si plusieurs correspondances (défaut: 1)",
    )
    parser.add_argument("--exact", action="store_true", help="Exiger une égalité stricte sur nom+prénom")
    parser.add_argument("--dry-run", action="store_true", help="N'écrit pas le fichier Markdown")
    return parser.parse_args()


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV introuvable: {csv_path}")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def find_matches(rows: list[dict[str, str]], query: str, exact: bool) -> list[dict[str, str]]:
    q_norm = _normalize(query)
    if not q_norm:
        return []

    matches: list[dict[str, str]] = []
    q_tokens = q_norm.split()

    for row in rows:
        nom = (row.get("nom") or "").strip()
        prenom = (row.get("prénom") or row.get("prenom") or "").strip()
        fullname = f"{prenom} {nom}".strip()
        fullname_norm = _normalize(fullname)

        if exact:
            if fullname_norm == q_norm:
                matches.append(row)
            continue

        if q_norm in fullname_norm:
            matches.append(row)
            continue

        if all(tok in fullname_norm for tok in q_tokens):
            matches.append(row)

    return matches


def fetch_person_page(page, person_url: str) -> dict[str, Any]:
    page.goto(person_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(3000)

    return page.evaluate(
        """
        () => {
          const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const normalizeTitleKey = (s) =>
            clean(s || '')
              .toLowerCase()
              .normalize('NFD')
              .replace(/[\\u0300-\\u036f]/g, '');
          const hasColClass = (el) => {
            const classes = Array.from(el.classList || []);
            return classes.some((c) => /^col($|-)/.test(c));
          };
          const extractLinks = (el) => {
            const links = [];
            const seen = new Set();
            const anchors = Array.from(el.querySelectorAll?.('a[href]') || []);
            for (const a of anchors) {
              const text = clean(a.innerText || a.textContent || '');
              const href = clean(a.href || '');
              if (!href || seen.has(href)) continue;
              seen.add(href);
              links.push({ text: text || href, url: href });
            }
            return links;
          };
          const extractRowCells = (row) => {
            const directDivChildren = Array.from(row.children || []).filter(
              (child) => child.tagName && child.tagName.toLowerCase() === 'div'
            );
            const cols = directDivChildren.filter((child) => hasColClass(child));
            const cells = (cols.length ? cols : directDivChildren)
              .map((child) => clean(child.innerText || ''))
              .filter(Boolean);
            return cells;
          };

          const docTitle = clean(document.title || '');
          let profileTitle = clean(document.querySelector('h1')?.innerText || '');
          if (!profileTitle && docTitle.includes('|')) {
            const parts = docTitle.split('|');
            profileTitle = clean(parts[parts.length - 1] || '');
          }
          if (!profileTitle) {
            profileTitle = clean(document.querySelector('h3')?.innerText || docTitle);
          }

          const sections = [];
          const excludedSubsections = new Set([
            'citer cette fiche',
            'corrections - compléments',
            'corrections - complements',
          ]);
          const headings = Array.from(document.querySelectorAll('h3'));
          for (const h of headings) {
            const title = clean(h.innerText);
            if (!title) continue;
            const titleKey = normalizeTitleKey(title);

            const blocks = [];
            const pendingTableRows = [];
            let skipSubsection = false;
            const flushPendingTable = () => {
              if (pendingTableRows.length === 0) return;
              blocks.push({ type: 'table', rows: [...pendingTableRows] });
              pendingTableRows.length = 0;
            };
            let n = h.nextElementSibling;
            while (n && n.tagName && n.tagName.toLowerCase() !== 'h3') {
              const tag = (n.tagName || '').toLowerCase();
              if (/^h[1-6]$/.test(tag)) {
                const headingText = clean(n.innerText || '').toLowerCase();
                if (excludedSubsections.has(headingText)) {
                  flushPendingTable();
                  skipSubsection = true;
                  n = n.nextElementSibling;
                  continue;
                }
                if (skipSubsection) {
                  skipSubsection = false;
                }
              }
              if (skipSubsection) {
                n = n.nextElementSibling;
                continue;
              }
              if (titleKey === 'ressources externes') {
                const links = extractLinks(n);
                if (links.length > 0) {
                  flushPendingTable();
                  blocks.push({ type: 'links', links });
                  n = n.nextElementSibling;
                  continue;
                }
              }
              const src = clean(n.getAttribute?.('src') || n.src || '');
              if (tag === 'img' && src) {
                flushPendingTable();
                blocks.push({
                  type: 'image',
                  url: src,
                  alt: clean(n.getAttribute?.('alt') || ''),
                });
                n = n.nextElementSibling;
                continue;
              }
              const nestedImages = Array.from(n.querySelectorAll?.('img[src]') || []);
              if (nestedImages.length > 0) {
                flushPendingTable();
                for (const img of nestedImages) {
                  const nestedSrc = clean(img.getAttribute?.('src') || img.src || '');
                  if (!nestedSrc || nestedSrc.startsWith('data:')) continue;
                  blocks.push({
                    type: 'image',
                    url: nestedSrc,
                    alt: clean(img.getAttribute?.('alt') || ''),
                  });
                }
              }

              const isRow = !!n.classList && n.classList.contains('row');
              if (isRow) {
                const cells = extractRowCells(n);
                if (cells.length > 0) {
                  pendingTableRows.push(cells);
                  n = n.nextElementSibling;
                  continue;
                }
              }
              const nestedRows = Array.from(n.querySelectorAll?.('.row') || []);
              if (nestedRows.length > 0) {
                for (const row of nestedRows) {
                  const cells = extractRowCells(row);
                  if (cells.length > 0) {
                    pendingTableRows.push(cells);
                  }
                }
                if (pendingTableRows.length > 0) {
                  n = n.nextElementSibling;
                  continue;
                }
              }

              flushPendingTable();
              const txt = clean(n.innerText);
              if (txt) blocks.push({ type: 'text', text: txt });
              n = n.nextElementSibling;
            }
            flushPendingTable();

            if (blocks.length > 0) {
              sections.push({ title, blocks });
            }
          }

          const sectionTitles = new Set(sections.map((s) => clean(s.title)));
          const sectionImages = {};
          const leadingImages = [];
          let currentSection = "";
          const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_ELEMENT);
          let node = walker.currentNode;
          while (node) {
            const tag = (node.tagName || '').toLowerCase();
            if (tag === 'h3') {
              const title = clean(node.innerText || '');
              currentSection = sectionTitles.has(title) ? title : "";
            } else if (tag === 'img') {
              const src = clean(node.getAttribute?.('src') || node.src || '');
              if (!src || src.startsWith('data:')) {
                node = walker.nextNode();
                continue;
              }
              const payload = { url: src, alt: clean(node.getAttribute?.('alt') || '') };
              if (currentSection) {
                if (!sectionImages[currentSection]) sectionImages[currentSection] = [];
                sectionImages[currentSection].push(payload);
              } else {
                leadingImages.push(payload);
              }
            }
            node = walker.nextNode();
          }

          let citation = '';
          const citationHeading = Array.from(document.querySelectorAll('h4')).find(
            (h) => clean(h.innerText).toLowerCase() === 'citer cette fiche'
          );
          if (citationHeading) {
            const citationParts = [];
            let n = citationHeading.nextElementSibling;
            while (n && n.tagName && !/^h[1-6]$/i.test(n.tagName)) {
              const txt = clean(n.innerText);
              if (txt) citationParts.push(txt);
              n = n.nextElementSibling;
            }
            citation = clean(citationParts.join(' '));
          }

          const bodyText = clean(document.body?.innerText || '');

          return {
            page_title: docTitle,
            profile_title: profileTitle,
            sections,
            section_images: sectionImages,
            leading_images: leadingImages,
            citation,
            body_excerpt: bodyText.slice(0, 3000),
          };
        }
        """
    )


def _markdown_table_from_rows(rows: list[list[str]]) -> list[str]:
    normalized = [[(cell or "").replace("|", r"\|").strip() for cell in row] for row in rows if row]
    if not normalized:
        return []
    width = max(len(row) for row in normalized)
    padded = [row + [""] * (width - len(row)) for row in normalized]
    header = padded[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in padded[1:])
    return lines


def _normalize_title_key(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _to_network_items(text: str) -> list[str]:
    raw = re.sub(r"^\s*réseau\s*", "", (text or "").strip(), flags=re.IGNORECASE)
    if not raw:
        return []
    chunks = re.findall(r"[^()]+?\(\d{4}(?:-\d{4})?\)", raw)
    if chunks:
        return [re.sub(r"\s+", " ", c).strip() for c in chunks if c.strip()]
    return [part.strip() for part in re.split(r"\s{2,}|;\s*", raw) if part.strip()]


def _extract_publication_date(citation: str) -> str:
    match = re.search(r"\bversion\s+du\s+(\d{2}\.\d{2}\.\d{4})\b", citation or "", flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _is_excluded_image_url(url: str) -> bool:
    path_name = Path(unquote(urlsplit(url).path)).name.lower()
    return path_name in EXCLUDED_IMAGE_FILENAMES


def build_markdown(
    selected: dict[str, str],
    details: dict[str, Any],
    query: str,
    csv_path: Path,
    person_url: str,
) -> str:
    now_iso = dt.datetime.now().isoformat(timespec="seconds")
    nom = (selected.get("nom") or "").strip()
    prenom = (selected.get("prénom") or selected.get("prenom") or "").strip()
    dates = (selected.get("dates") or "").strip()
    mandats = (selected.get("mandats") or "").strip()
    projet = (selected.get("Projet") or selected.get("projet") or "").strip()

    display_name = f"{prenom} {nom}".strip()
    title = display_name or details.get("profile_title") or "Fiche EliteSuisses"

    sections_raw = details.get("sections") or []
    sections: list[dict[str, Any]] = []
    section_index_by_title: dict[str, int] = {}
    for sec in sections_raw:
        sec_title = (sec.get("title") or "").strip()
        if not sec_title:
            continue
        key = _normalize_title_key(sec_title)
        blocks = list(sec.get("blocks") or [])
        existing_index = section_index_by_title.get(key)
        if existing_index is None:
            section_index_by_title[key] = len(sections)
            sections.append({"title": sec_title, "blocks": blocks})
            continue
        sections[existing_index]["blocks"].extend(blocks)
    display_name_key = _normalize_title_key(display_name)
    network_fallback_items: list[str] = []
    for sec in sections:
        if _normalize_title_key(sec.get("title") or "") != display_name_key:
            continue
        for block in sec.get("blocks") or []:
            if (block.get("type") or "").strip() != "text":
                continue
            text = (block.get("text") or "").strip()
            if not text:
                continue
            for item in _to_network_items(text):
                if item and item not in network_fallback_items:
                    network_fallback_items.append(item)
    details_text_parts: list[str] = []
    citation = (details.get("citation") or "").strip()
    date_publication = _extract_publication_date(citation)
    for sec in sections:
        sec_title = (sec.get("title") or "").strip()
        if sec_title:
            details_text_parts.append(sec_title)
        for block in (sec.get("blocks") or []):
            block_type = (block.get("type") or "").strip()
            if block_type == "text":
                sec_text = (block.get("text") or "").strip()
                if sec_text:
                    details_text_parts.append(sec_text)
            elif block_type == "table":
                for row in block.get("rows") or []:
                    for cell in row:
                        cell_text = str(cell or "").strip()
                        if cell_text:
                            details_text_parts.append(cell_text)
            elif block_type == "links":
                for link in block.get("links") or []:
                    link_text = str(link.get("text") or "").strip()
                    link_url = str(link.get("url") or "").strip()
                    if link_text:
                        details_text_parts.append(link_text)
                    if link_url:
                        details_text_parts.append(link_url)
            elif block_type == "list":
                for item in block.get("items") or []:
                    item_text = str(item or "").strip()
                    if item_text:
                        details_text_parts.append(item_text)
    if citation:
        details_text_parts.append(citation)
    if not details_text_parts:
        details_text_parts.append((details.get("body_excerpt") or "").strip())
    language_distribution = _compute_language_distribution("\n\n".join(part for part in details_text_parts if part))

    lines: list[str] = [
        "---",
        f'title: "{_yaml_quote(title)}"',
        f'date_publication: "{_yaml_quote(date_publication)}"',
        f'date_consultation: "{now_iso}"',
        f'url: "{_yaml_quote(person_url)}"',
        f'citation: "{_yaml_quote(citation)}"',
        f'language_distribution: "{_yaml_quote(language_distribution)}"',
        'transformation_by: "skill fetch-elitesuisse-person-details"',
        "---",
        "",
        "## Page 1",
        "",
        f"# {title}",
        "",
        f"- Requête: {query}",
        f"- Nom: {nom}",
        f"- Prénom: {prenom}",
        f"- Dates: {dates}",
        f"- Mandats (index): {mandats}",
        f"- Projet (index): {projet}",
        f"- URL: {person_url}",
        "",
        "## Détails de la fiche",
        "",
    ]
    section_images = details.get("section_images") or {}
    leading_images = details.get("leading_images") or []
    emitted_image_urls: set[str] = set()
    for image in leading_images:
        image_url = (image.get("url") or "").strip()
        if not image_url or _is_excluded_image_url(image_url) or image_url in emitted_image_urls:
            continue
        image_alt = (image.get("alt") or "Illustration").strip() or "Illustration"
        lines.append(f"![{image_alt}]({image_url})")
        lines.append("")
        emitted_image_urls.add(image_url)

    if sections:
        for sec in sections:
            sec_title = (sec.get("title") or "").strip()
            blocks = sec.get("blocks") or []
            if not sec_title or not blocks:
                continue
            section_key = _normalize_title_key(sec_title)
            section_seen_links: set[str] = set()
            section_seen_network_items: set[str] = set()
            lines.append(f"### {sec_title}")
            lines.append("")
            if section_key == "ressources externes":
                emitted_links = False
                for block in blocks:
                    if (block.get("type") or "").strip() != "links":
                        continue
                    for link in block.get("links") or []:
                        link_text = (link.get("text") or "").strip()
                        link_url = (link.get("url") or "").strip()
                        if not link_url or link_url in section_seen_links:
                            continue
                        section_seen_links.add(link_url)
                        label = link_text or link_url
                        lines.append(f"- [{label}]({link_url})")
                        emitted_links = True
                if emitted_links:
                    lines.append("")
                continue
            if section_key == "reseau":
                reseau_items: list[str] = []
                for block in blocks:
                    block_type = (block.get("type") or "").strip()
                    if block_type == "list":
                        for item in block.get("items") or []:
                            item_text = str(item or "").strip()
                            if item_text:
                                reseau_items.append(item_text)
                    elif block_type == "text":
                        reseau_items.extend(_to_network_items((block.get("text") or "").strip()))
                deduped_reseau: list[str] = []
                for item in reseau_items:
                    if not item or item in section_seen_network_items:
                        continue
                    section_seen_network_items.add(item)
                    deduped_reseau.append(item)
                non_url_items = [item for item in deduped_reseau if not item.startswith(("http://", "https://"))]
                if not non_url_items and network_fallback_items:
                    deduped_reseau = [item for item in network_fallback_items if item not in section_seen_network_items]
                for item in deduped_reseau:
                    section_seen_network_items.add(item)
                    lines.append(f"- {item}")
                if deduped_reseau:
                    lines.append("")
                continue
            for block in blocks:
                block_type = (block.get("type") or "").strip()
                if block_type == "text":
                    text = (block.get("text") or "").strip()
                    if text:
                        lines.append(text)
                        lines.append("")
                    continue
                if block_type == "table":
                    table_lines = _markdown_table_from_rows(block.get("rows") or [])
                    if table_lines:
                        lines.extend(table_lines)
                        lines.append("")
                    continue
                if block_type == "links":
                    links = block.get("links") or []
                    emitted_any_link = False
                    for link in links:
                        link_text = (link.get("text") or "").strip()
                        link_url = (link.get("url") or "").strip()
                        if not link_url or link_url in section_seen_links:
                            continue
                        section_seen_links.add(link_url)
                        label = link_text or link_url
                        lines.append(f"- [{label}]({link_url})")
                        emitted_any_link = True
                    if emitted_any_link:
                        lines.append("")
                    continue
                if block_type == "list":
                    items = [str(item).strip() for item in (block.get("items") or []) if str(item).strip()]
                    emitted_any_item = False
                    for item in items:
                        if item in section_seen_network_items:
                            continue
                        section_seen_network_items.add(item)
                        lines.append(f"- {item}")
                        emitted_any_item = True
                    if emitted_any_item:
                        lines.append("")
                    continue
                if block_type == "image":
                    image_url = (block.get("url") or "").strip()
                    if not image_url or _is_excluded_image_url(image_url) or image_url in emitted_image_urls:
                        continue
                    image_alt = (block.get("alt") or "Illustration").strip() or "Illustration"
                    lines.append(f"![{image_alt}]({image_url})")
                    lines.append("")
                    emitted_image_urls.add(image_url)
            for image in section_images.get(sec_title, []):
                image_url = (image.get("url") or "").strip()
                if not image_url or _is_excluded_image_url(image_url) or image_url in emitted_image_urls:
                    continue
                image_alt = (image.get("alt") or "Illustration").strip() or "Illustration"
                lines.append(f"![{image_alt}]({image_url})")
                lines.append("")
                emitted_image_urls.add(image_url)
    else:
        excerpt = (details.get("body_excerpt") or "").strip()
        lines.append(excerpt or "Aucun contenu textuel extrait.")
        lines.append("")
        for image in leading_images:
            image_url = (image.get("url") or "").strip()
            if not image_url or _is_excluded_image_url(image_url) or image_url in emitted_image_urls:
                continue
            image_alt = (image.get("alt") or "Illustration").strip() or "Illustration"
            lines.append(f"![{image_alt}]({image_url})")
            lines.append("")
            emitted_image_urls.add(image_url)

    return "\n".join(lines).rstrip() + "\n"


def _safe_image_filename(url: str, index: int) -> str:
    parsed = urlsplit(url)
    raw_name = Path(unquote(parsed.path)).name
    stem = Path(raw_name).stem if raw_name else f"image_{index:03d}"
    suffix = Path(raw_name).suffix.lower() if raw_name else ""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or f"image_{index:03d}"
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".tif", ".tiff", ".bmp", ".avif"}:
        suffix = ".jpg"
    return f"{index:03d}_{stem}{suffix}"


def _is_probable_content_image(url: str) -> bool:
    if _is_excluded_image_url(url):
        return False
    parsed = urlsplit(url)
    host = (parsed.netloc or "").lower()
    if any(marker in host for marker in TRACKING_HOST_MARKERS):
        return False
    path = (parsed.path or "").lower()
    if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp", ".tif", ".tiff")):
        return True
    return "/download/" in path


def _resolve_image_url(url: str, base_url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("//"):
        return "https:" + raw
    if base_url:
        return urljoin(base_url, raw)
    return raw


def _download_image_via_page(page: Any, image_url: str, out_img: Path, timeout_ms: int = 30000) -> bool:
    page.set_default_timeout(timeout_ms)
    result = page.evaluate(
        """
        async ({ imageUrl }) => {
          try {
            const response = await fetch(imageUrl, {
              credentials: 'include',
              cache: 'force-cache',
            });
            if (!response.ok) {
              return { ok: false, error: `HTTP ${response.status}` };
            }
            const buffer = await response.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            let binary = '';
            const chunkSize = 0x8000;
            for (let i = 0; i < bytes.length; i += chunkSize) {
              const chunk = bytes.subarray(i, i + chunkSize);
              binary += String.fromCharCode(...chunk);
            }
            return { ok: true, bodyBase64: btoa(binary) };
          } catch (error) {
            return { ok: false, error: String(error) };
          }
        }
        """,
        {"imageUrl": image_url},
    )
    if not result or not result.get("ok"):
        return False
    payload = result.get("bodyBase64") or ""
    if not payload:
        return False
    import base64
    out_img.write_bytes(base64.b64decode(payload))
    return True


def download_and_rewrite_images(
    md: str,
    md_out_path: Path,
    images_root: Path,
    page: Any | None = None,
    base_url: str | None = None,
) -> tuple[str, int, int, list[Path]]:
    pattern = re.compile(r"!\[([^]]*)]\(([^)\s]+)\)")
    matches = list(pattern.finditer(md))
    if not matches:
        return md, 0, 0, []

    target_dir = images_root / md_out_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_url_pairs: list[tuple[str, str]] = []
    seen = set()
    for m in matches:
        raw_url = m.group(2).strip()
        resolved_url = _resolve_image_url(raw_url, base_url)
        if not resolved_url or resolved_url in seen:
            continue
        seen.add(resolved_url)
        unique_url_pairs.append((raw_url, resolved_url))

    url_to_local: dict[str, str] = {}
    local_images: list[Path] = []
    downloaded = 0
    failed = 0

    for index, (raw_url, resolved_url) in enumerate(unique_url_pairs, start=1):
        if not _is_probable_content_image(resolved_url):
            continue
        out_img = target_dir / _safe_image_filename(resolved_url, index)
        try:
            if not out_img.exists():
                if page is not None:
                    ok = _download_image_via_page(page, resolved_url, out_img)
                    if not ok:
                        raise RuntimeError("téléchargement image via navigateur impossible")
                else:
                    req = Request(resolved_url, headers={"User-Agent": "Mozilla/5.0 (fetch_elitesuisse_person_details)"})
                    with urlopen(req, timeout=20) as response:
                        out_img.write_bytes(response.read())
                downloaded += 1
            local_images.append(out_img)
            rel_path = str(out_img.relative_to(md_out_path.parent)).replace("\\", "/")
            url_to_local[raw_url] = rel_path
            url_to_local[resolved_url] = rel_path
        except Exception:
            failed += 1

    def _replace(m: re.Match[str]) -> str:
        alt, raw_url = m.group(1), m.group(2).strip()
        resolved_url = _resolve_image_url(raw_url, base_url)
        lookup_url = raw_url if raw_url in url_to_local else resolved_url
        url = lookup_url or raw_url
        if _is_excluded_image_url(url):
            return ""
        local = url_to_local.get(url)
        if not local:
            return m.group(0)
        return f"![{alt}]({local})"

    rewritten = pattern.sub(_replace, md)
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    return rewritten, downloaded, failed, local_images


def register_output_in_db(
    out_path: Path,
    person_url: str,
    selected: dict[str, str],
    details: dict[str, Any],
    image_paths: list[Path],
) -> None:
    if not DB_AVAILABLE:
        return

    nom = (selected.get("nom") or "").strip()
    prenom = (selected.get("prénom") or selected.get("prenom") or "").strip()
    person_id = _extract_person_id(person_url)
    identifiant_source = f"SRC-ELITESUISSE-PERSON-{_slugify(f'{prenom}_{nom}').upper()}-{person_id.upper()}"
    titre = f"EliteSuisses: {(prenom + ' ' + nom).strip() or details.get('profile_title') or 'Personne'}"

    try:
        con = get_db_connection()
    except Exception as exc:
        print(f"[WARN] SQLite indisponible pour {out_path.name}: {exc}")
        return

    try:
        result = register_source_document(
            con,
            origin_path=out_path,
            identifiant_source=identifiant_source,
            titre=titre,
            url=person_url,
            auteurs=["EliteSuisses"],
            pertinence=0.65,
            type_source="secondaire",
            lisible=True,
            nombre_pages=1,
            categorie="autre",
            ner_status=1
        )
        if result.get("action") == "error":
            print(f"[WARN] Insertion SQLite ignorée pour {out_path.name}: {result.get('reason', 'erreur inconnue')}")
            return
        for image_path in image_paths:
            storage_status = register_source_document(
                con,
                origin_path=image_path,
                parent_path=out_path,
                ner_status=0,
            )
            if storage_status.get("action") == "error":
                print(
                    f"[WARN] Insertion SQLite ignorée pour {image_path.name}: "
                    f"{storage_status.get('reason', 'erreur inconnue')}"
                )
    finally:
        con.close()


def main() -> int:
    args = parse_args()

    rows = load_rows(args.csv_path)
    matches = find_matches(rows, args.name, args.exact)

    if not matches:
        print(
            json.dumps(
                {
                    "query": args.name,
                    "found": False,
                    "message": "Personne non trouvée dans le CSV d'index.",
                    "csv": str(args.csv_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    idx = max(1, args.candidate_index)
    if idx > len(matches):
        idx = 1
    selected = matches[idx - 1]

    person_url = (selected.get("URL") or selected.get("url") or "").strip()
    if not person_url:
        print(
            json.dumps(
                {
                    "query": args.name,
                    "found": True,
                    "error": "Personne trouvée mais URL absente dans le CSV.",
                    "matches": len(matches),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    nom = (selected.get("nom") or "").strip()
    prenom = (selected.get("prénom") or selected.get("prenom") or "").strip()
    person_id = _extract_person_id(person_url)
    out_name = f"elitesuisse_personne_{_slugify(f'{prenom}_{nom}')}_{person_id}.md"

    if args.dry_run:
        print(
            json.dumps(
                {
                    "query": args.name,
                    "found": True,
                    "matches": len(matches),
                    "selected_index": idx,
                    "selected": {
                        "nom": nom,
                        "prenom": prenom,
                        "dates": selected.get("dates", ""),
                        "url": person_url,
                    },
                    "output_file": str((args.out_dir / out_name)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / out_name
    images_root = args.out_dir / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        details = fetch_person_page(page, person_url)
        markdown = build_markdown(selected, details, args.name, args.csv_path, person_url)
        markdown, images_downloaded, images_failed, image_paths = download_and_rewrite_images(
            markdown,
            out_path,
            images_root,
            page=page,
            base_url=person_url,
        )
        page.close()

    out_path.write_text(markdown, encoding="utf-8")
    register_output_in_db(out_path, person_url, selected, details, image_paths)

    print(
        json.dumps(
            {
                "query": args.name,
                "found": True,
                "matches": len(matches),
                "selected_index": idx,
                "output": str(out_path),
                "url": person_url,
                "images_downloaded": images_downloaded,
                "images_failed": images_failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

