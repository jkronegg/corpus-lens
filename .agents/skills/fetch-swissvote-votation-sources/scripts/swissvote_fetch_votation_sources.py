#!/usr/bin/env python3
"""Fetch official Swissvotes sources for one votation id.

This script automates the workflow described in the skill:
- Create sources/swissvotes/votation_<id>
- Download vote page HTML
- Save a Markdown snapshot of the page
- Download official chronology and Federal Council message documents
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from http.cookiejar import CookieJar
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE_URL = "https://swissvotes.ch/vote/{votation_id}.00"
DEFAULT_OUTPUT_ROOT = Path("sources/swissvotes")
DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; fetch-swissvote-votation-sources/1.0)"
SKILL_NAME = "fetch-swissvote-votation-sources"

# ---------------------------------------------------------------------------
# Intégration base de données SQLite
# ---------------------------------------------------------------------------
_SKILL_REPO_ROOT = Path(__file__).resolve().parents[4]  # histoire_suisse/
_DB_SCRIPTS_DIR = (
    _SKILL_REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
)
if str(_DB_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_DB_SCRIPTS_DIR))

try:
    from db import get_connection as _get_db_connection, upsert_source as _db_upsert_source  # type: ignore
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

_PRIMARY_BINARY_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".ods",
    ".csv",
    ".tsv",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
}

_KIND_SOURCE_FAMILY: dict[str, str] = {
    "votation_snapshot": "votation_snapshot",
    "chronologie_officielle": "chronologie_officielle",
    "chronologie_officielle_markdown": "chronologie_officielle",
    "message_conseil_federal": "message_conseil_federal",
    "debat_parlementaire": "debat_parlementaire",
    "texte_soumis_au_vote": "texte_soumis_au_vote",
    "resultats_par_domaine": "resultats_par_domaine",
}

_FAMILY_TITRE: dict[str, str] = {
    "votation_snapshot": "Votation {id}.00 – Swissvotes",
    "chronologie_officielle": "Chronologie officielle – Votation {id}.00",
    "message_conseil_federal": "Message du Conseil fédéral – Votation {id}.00",
    "debat_parlementaire": "Débat parlementaire – Votation {id}.00",
    "texte_soumis_au_vote": "Texte soumis au vote – Votation {id}.00",
    "resultats_par_domaine": "Résultats par domaine – Votation {id}.00",
}


@dataclass
class ExtractedLink:
    label: str
    url: str


@dataclass
class DownloadedDocument:
    kind: str
    source_url: str
    file_path: str


class _TextAndLinksParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_script = False
        self._in_style = False
        self._current_href: Optional[str] = None
        self.text_chunks: list[str] = []
        self.links: list[ExtractedLink] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_dict = dict(attrs)
        if tag == "script":
            self._in_script = True
            return
        if tag == "style":
            self._in_style = True
            return
        if tag == "a":
            self._current_href = attrs_dict.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_script = False
            return
        if tag == "style":
            self._in_style = False
            return
        if tag == "a":
            self._current_href = None

    def handle_data(self, data: str) -> None:
        if self._in_script or self._in_style:
            return
        text = _norm_ws(data)
        if not text:
            return

        self.text_chunks.append(text)
        if self._current_href:
            self.links.append(ExtractedLink(label=text, url=self._current_href))


class _AlternateLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.french_href: Optional[str] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in {"link", "a"} or self.french_href is not None:
            return

        attrs_dict = {str(key).lower(): value for key, value in attrs}
        href = attrs_dict.get("href")
        rel = _norm_ws(attrs_dict.get("rel", "")).lower()
        lang = _norm_ws(attrs_dict.get("lang", "") or attrs_dict.get("hreflang", "")).lower()

        rel_tokens = {token for token in rel.split(" ") if token}
        if href and "alternate" in rel_tokens and lang == "fr":
            self.french_href = href


def _norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _slug_ascii(value: str) -> str:
    cleaned = _norm_ws(value).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "file"


def _yaml_quote(value: str) -> str:
    escaped = (value or "").replace('"', "'")
    return f'"{escaped}"'


def _build_front_matter(*, titre: str, url: str, date_consultation: str) -> str:
    return "\n".join(
        [
            "---",
            f"titre: {_yaml_quote(titre)}",
            f"url: {_yaml_quote(url)}",
            f"date_consultation: {_yaml_quote(date_consultation)}",
            f"author: {_yaml_quote("skill " + SKILL_NAME)}",
            f"language_distribution: \"fr:100\"",
            "---",
            "",
        ]
    )


def _fetch_url(url: str, *, timeout_seconds: int) -> bytes:
    payload, _ = _fetch_url_with_final_url(url, timeout_seconds=timeout_seconds)
    return payload


def _fetch_url_with_final_url(url: str, *, timeout_seconds: int) -> tuple[bytes, str]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with opener.open(request, timeout=timeout_seconds) as response:
        return response.read(), response.geturl()


def _extract_french_alternate_url(html_text: str, page_url: str) -> Optional[str]:
    parser = _AlternateLinkParser()
    parser.feed(html_text)
    if not parser.french_href:
        return None
    return urljoin(page_url, parser.french_href)


def _derive_french_url_from_german_path(url: str) -> Optional[str]:
    parsed = urlparse(url)
    path = parsed.path or ""
    if "/ch/d/" not in path:
        return None
    return urljoin(url, path.replace("/ch/d/", "/ch/f/", 1))


def _is_probably_same_document(initial_url: str, final_url: str) -> bool:
    initial_path = urlparse(initial_url).path
    final_path = urlparse(final_url).path

    initial_name = Path(initial_path).name
    final_name = Path(final_path).name

    if initial_name and final_name and initial_name == final_name:
        return True

    if "/pore/rf/cr/" in initial_path and "/pore/rf/cr/" in final_path:
        return True

    return False


def _resolve_french_alternate_page(
    *,
    initial_url: str,
    initial_payload: bytes,
    timeout_seconds: int,
) -> tuple[bytes, str]:
    try:
        html_text = initial_payload.decode("utf-8", errors="replace")
    except Exception:
        return initial_payload, initial_url

    candidate_urls: list[str] = []

    french_alternate_url = _extract_french_alternate_url(html_text, initial_url)
    if french_alternate_url:
        candidate_urls.append(french_alternate_url)

    derived_french_url = _derive_french_url_from_german_path(initial_url)
    if derived_french_url and derived_french_url not in candidate_urls:
        candidate_urls.append(derived_french_url)

    for candidate_url in candidate_urls:
        try:
            payload, final_url = _fetch_url_with_final_url(candidate_url, timeout_seconds=timeout_seconds)
            if _is_probably_same_document(initial_url, final_url):
                return payload, final_url
        except Exception:
            continue

    return initial_payload, initial_url


def _fetch_prefer_french_page(url: str, *, timeout_seconds: int) -> tuple[bytes, str]:
    payload, effective_url = _fetch_url_with_final_url(url, timeout_seconds=timeout_seconds)
    return _resolve_french_alternate_page(
        initial_url=effective_url,
        initial_payload=payload,
        timeout_seconds=timeout_seconds,
    )


def _extract_unique_links(raw_links: list[ExtractedLink], page_url: str) -> list[ExtractedLink]:
    seen: set[tuple[str, str]] = set()
    out: list[ExtractedLink] = []
    for item in raw_links:
        resolved = urljoin(page_url, item.url)
        normalized = ExtractedLink(label=_norm_ws(item.label), url=resolved)
        key = (normalized.label, normalized.url)
        if not normalized.label or not normalized.url or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _extract_unique_text(raw_texts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for chunk in raw_texts:
        text = _norm_ws(chunk)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _html_fragment_to_markdown_text(fragment: str, page_url: str) -> str:
    def _anchor_repl(match: re.Match[str]) -> str:
        href = _norm_ws(match.group(1))
        label = _strip_html_tags(match.group(2)) or "Lien"
        return f"[{label}]({urljoin(page_url, href)})"

    text = re.sub(
        r'(?is)<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        _anchor_repl,
        fragment,
    )
    text = re.sub(r"(?i)<br\s*/?>", " ; ", text)
    text = _strip_html_tags(text)
    return text or "-"


def _extract_key_value_sections(html_text: str, page_url: str) -> list[tuple[str, list[tuple[str, str]]]]:
    sections: list[tuple[str, list[tuple[str, str]]]] = []

    table_html_list = re.findall(
        r'(?is)<table[^>]*class=["\'][^"\']*collapsible[^"\']*["\'][^>]*>(.*?)</table>',
        html_text,
    )

    for table_html in table_html_list:
        heading_match = re.search(r"(?is)<thead[^>]*>.*?<th[^>]*>(.*?)</th>.*?</thead>", table_html)
        section_title = _strip_html_tags(heading_match.group(1)) if heading_match else "Section"

        body_match = re.search(r"(?is)<tbody[^>]*>(.*?)</tbody>", table_html)
        body_html = body_match.group(1) if body_match else table_html
        row_html_list = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body_html)

        pairs: list[tuple[str, str]] = []
        for row_html in row_html_list:
            header_cells = re.findall(r"(?is)<th[^>]*>(.*?)</th>", row_html)
            value_cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", row_html)

            key_html = ""
            value_html = ""

            if header_cells and value_cells:
                key_html = header_cells[0]
                value_html = value_cells[0]
            elif len(value_cells) >= 2:
                key_html = value_cells[0]
                value_html = value_cells[1]
            elif len(value_cells) == 1:
                key_html = value_cells[0]
                value_html = ""

            key = _strip_html_tags(key_html)
            value = _html_fragment_to_markdown_text(value_html, page_url)

            if key:
                pairs.append((key, value))

        if pairs:
            sections.append((section_title, pairs))

    return sections


def _extract_official_links_from_html(
    html: str,
    page_url: str,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    def _extract_href_for_anchor_class(target_class: str) -> Optional[str]:
        # Accepte classes multiples, quotes simples/doubles, et attributs dans n'importe quel ordre.
        for anchor_match in re.finditer(r"(?is)<a\b([^>]+)>", html):
            attrs = anchor_match.group(1)
            class_match = re.search(r"(?i)\bclass\s*=\s*(['\"])(.*?)\1", attrs)
            href_match = re.search(r"(?i)\bhref\s*=\s*(['\"])(.*?)\1", attrs)
            if not class_match or not href_match:
                continue

            class_tokens = [token.strip().lower() for token in class_match.group(2).split() if token.strip()]
            if target_class.lower() not in class_tokens:
                continue
            return href_match.group(2)

        return None

    chrono_href = _extract_href_for_anchor_class("bk_chrono")
    message_href = _extract_href_for_anchor_class("federal-council-message")
    debate_href = _extract_href_for_anchor_class("parliamentary-debate")
    voting_text_href = _extract_href_for_anchor_class("voting-text")
    results_by_domain_href = _extract_href_for_anchor_class("results-by-domain")

    chrono_url = urljoin(page_url, chrono_href) if chrono_href else None
    message_url = urljoin(page_url, message_href) if message_href else None
    debate_url = urljoin(page_url, debate_href) if debate_href else None
    voting_text_url = urljoin(page_url, voting_text_href) if voting_text_href else None
    results_by_domain_url = urljoin(page_url, results_by_domain_href) if results_by_domain_href else None
    return chrono_url, message_url, debate_url, voting_text_url, results_by_domain_url


def _extract_official_links_fallback(
    links: list[ExtractedLink],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    chrono_url: Optional[str] = None
    message_url: Optional[str] = None
    debate_url: Optional[str] = None
    voting_text_url: Optional[str] = None
    results_by_domain_url: Optional[str] = None

    for item in links:
        label = item.label.lower()
        url = item.url.lower()

        if chrono_url is None and (
            "chronologie" in label
            or "chronology" in label
            or "bk.admin.ch/ch/d/pore/rf/cr/" in url
            or "bk.admin.ch/ch/f/pore/rf/cr/" in url
        ):
            chrono_url = item.url

        if message_url is None and (
            "botschaft" in label
            or "message du conseil" in label
            or "federal council" in label
            or "botschaft" in url
            or "/botschaft-" in url
        ):
            message_url = item.url

        if debate_url is None and (
            "débat parlementaire" in label
            or "debat parlementaire" in label
            or "parliamentary debate" in label
            or "parlamentsberatung" in label
            or "parlamentsberatung" in url
        ):
            debate_url = item.url

        if voting_text_url is None and (
            "texte soumis" in label
            or "voting text" in label
            or "abstimmungstext" in label
            or "abstimmungstext" in url
            or "/abstimmungstext-" in url
        ):
            voting_text_url = item.url

        if results_by_domain_url is None and (
            "résultats par canton" in label
            or "resultats par canton" in label
            or "résultats" in label and "excel" in label
            or "resultats" in label and "excel" in label
            or "results by" in label
            or "results-by-domain" in url
            or "staatsebenen" in url
            or url.endswith(".xlsx")
        ):
            results_by_domain_url = item.url

        if chrono_url and message_url and debate_url and voting_text_url and results_by_domain_url:
            break

    return chrono_url, message_url, debate_url, voting_text_url, results_by_domain_url


def _render_markdown(vote_url: str, html_text: str, votation_id: int) -> str:
    sections = _extract_key_value_sections(html_text, vote_url)
    consultation_ts = datetime.now().isoformat()
    title = f"Votation {votation_id}.00 - Swissvotes"

    lines: list[str] = [
        _build_front_matter(
            titre=title,
            url=vote_url,
            date_consultation=consultation_ts,
        ).rstrip(),
        f"# {title}",
        "",
        f"- Source: {vote_url}",
        f"- Date de consultation: {consultation_ts}",
        f"- Sections tableau extraites: {len(sections)}",
        "",
        "## Donnees structurees (tableaux cle/valeur)",
        "",
    ]

    if not sections:
        lines.extend(
            [
                "Aucun tableau `cle/valeur` n'a pu etre extrait automatiquement depuis la page.",
                "",
                "## Extrait texte",
                "",
                _strip_html_tags(html_text)[:4000],
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    for section_title, pairs in sections:
        lines.append(f"### {section_title}")
        lines.append("")
        lines.append("| Cle | Valeur |")
        lines.append("|---|---|")
        for key, value in pairs:
            key_cell = _norm_ws(key).replace("|", "\\|")
            value_cell = _norm_ws(value).replace("|", "\\|")
            lines.append(f"| {key_cell} | {value_cell} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _download_document(
    url: str,
    destination_dir: Path,
    filename_prefix: str,
    timeout_seconds: int,
    payload: bytes | None = None,
) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".bin"
    path = destination_dir / f"{filename_prefix}{suffix}"
    content = payload if payload is not None else _fetch_url(url, timeout_seconds=timeout_seconds)
    path.write_bytes(content)
    return path


def _strip_html_tags(fragment: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", fragment)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    return _norm_ws(text)


def _convert_chronology_html_to_markdown(html_text: str, source_url: str, votation_id: int) -> str:
    heading_matches = re.findall(r"(?is)<h2[^>]*>(.*?)</h2>", html_text)
    heading_candidates = [_strip_html_tags(match) for match in heading_matches if _strip_html_tags(match)]
    title = "Chronologie officielle"
    for candidate in heading_candidates:
        if "chronolog" in candidate.lower():
            title = candidate
            break
    if title == "Chronologie officielle" and heading_candidates:
        title = heading_candidates[-1]

    table_match = re.search(r"(?is)<table[^>]*>(.*?)</table>", html_text)
    parsed_rows: list[list[str]] = []

    if table_match:
        table_html = table_match.group(1)
        row_html_list = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", table_html)
        for row_html in row_html_list:
            cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_html)
            if not cells:
                continue
            row = [(_strip_html_tags(cell) or "-") for cell in cells]
            parsed_rows.append(row)

    consultation_ts = datetime.now().isoformat()
    lines: list[str] = [
        _build_front_matter(
            titre=f"Chronologie officielle - Votation {votation_id}.00",
            url=source_url,
            date_consultation=consultation_ts,
        ).rstrip(),
        f"# Chronologie officielle - Votation {votation_id}.00",
        "",
        f"- Source: {source_url}",
        f"- Date de consultation: {consultation_ts}",
        f"- Titre: {title}",
        "",
    ]

    if not parsed_rows:
        lines.extend(
            [
                "Aucune table de chronologie n'a pu etre extraite automatiquement.",
                "",
                "## Extrait texte",
                "",
                _strip_html_tags(html_text)[:4000],
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    max_cols = max(len(row) for row in parsed_rows)
    normalized_rows = [row + ["-"] * (max_cols - len(row)) for row in parsed_rows]

    if max_cols == 1:
        headers = ["Chronologie"]
    elif max_cols == 2:
        headers = ["Chronologie", "Date"]
    else:
        headers = ["Chronologie", "Date", "Reference"] + [f"Colonne {idx}" for idx in range(4, max_cols + 1)]

    lines.append("## Tableau de chronologie")
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in normalized_rows:
        escaped = [_norm_ws(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_chronology_markdown(
    *,
    source_url: str,
    raw_payload: bytes,
    destination_dir: Path,
    votation_id: int,
) -> Path:
    suffix = Path(urlparse(source_url).path).suffix.lower()
    markdown_path = destination_dir / "chronologie_officielle.md"

    if suffix in (".html", ".htm", ""):
        html_text = raw_payload.decode("utf-8", errors="replace")
        markdown = _convert_chronology_html_to_markdown(html_text, source_url, votation_id)
    else:
        consultation_ts = datetime.now().isoformat()
        markdown = "\n".join(
            [
                _build_front_matter(
                    titre=f"Chronologie officielle - Votation {votation_id}.00",
                    url=source_url,
                    date_consultation=consultation_ts,
                ).rstrip(),
                f"# Chronologie officielle - Votation {votation_id}.00",
                "",
                f"- Source: {source_url}",
                f"- Date de consultation: {consultation_ts}",
                "",
                "Le format source n'est pas HTML. Consultez le fichier binaire telecharge pour le contenu integral.",
                "",
            ]
        )

    markdown_path.write_text(markdown, encoding="utf-8")
    return markdown_path


def _is_html_like_url(url: str) -> bool:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix in ("", ".html", ".htm")


def _md5_file(path: Path) -> str:
    """Calcule le hash MD5 d'un fichier (identifiant_technique)."""
    digest = hashlib.md5()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _to_repo_rel_posix(path: Path) -> str:
    """Chemin POSIX relatif à la racine du dépôt."""
    try:
        return path.resolve().relative_to(_SKILL_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _is_primary_binary_document(path: Path) -> bool:
    return path.suffix.lower() in _PRIMARY_BINARY_EXTENSIONS


def _kind_family(kind: str) -> str:
    return _KIND_SOURCE_FAMILY.get(kind, kind)


def _build_identifiant_source(votation_id: int, family: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "-", family.upper()).strip("-")
    return f"SRC-SWISSVOTES-{votation_id}-{token}"


def _build_source_entry_from_family(
    *,
    votation_id: int,
    family: str,
    items: list[tuple[Path, str, str]],
) -> dict | None:
    if not items:
        return None

    principal_path, principal_kind, principal_url = sorted(
        items,
        key=lambda item: (
            0 if _is_primary_binary_document(item[0]) else 1,
            0 if item[0].suffix.lower() == ".md" else 1,
            item[0].name.lower(),
        ),
    )[0]

    derived_documents = []
    for path, _, _ in sorted(items, key=lambda item: item[0].name.lower()):
        if path.resolve() == principal_path.resolve():
            continue
        derived_documents.append(
            {
                "fichier": path.name,
                "path_relatif": path.relative_to(principal_path.parent).as_posix(),
                "author": "skill " + SKILL_NAME,
            }
        )

    titre_template = _FAMILY_TITRE.get(family, "Document Swissvotes – Votation {id}.00")
    has_markdown = any(path.suffix.lower() == ".md" for path, _, _ in items)

    return {
        "identifiant_technique": _md5_file(principal_path),
        "identifiant_source": _build_identifiant_source(votation_id, family),
        "titre": titre_template.format(id=votation_id),
        "date_publication": "0000-00-00",
        "date_consultation": datetime.now().strftime("%Y-%m-%d"),
        "origine": _to_repo_rel_posix(principal_path),
        "auteurs": [],
        "periodes": [],
        "ISBN": "",
        "ISSN": "",
        "DOI": "",
        "URL": principal_url,
        "langues": "fr:100" if has_markdown else None,
        "pertinence": 0.8,
        "type_source": "primaire",
        "lisible": True,
        "nombre_pages": -1,
        "categorie": "document officiel",
        "extrait_brut": "",
        "resume": "",
    }


def _upsert_all_downloaded_in_db(
    *,
    downloaded: list[DownloadedDocument],
    votation_snapshot_path: Path,
    votation_snapshot_url: str,
    votation_id: int,
) -> None:
    """Insère ou met à jour dans SQLite chaque source téléchargée et ses documents liés."""
    if not _DB_AVAILABLE:
        print("[WARN] Module db non disponible ; insertion SQLite ignorée.")
        return

    items: list[tuple[Path, str, str]] = []
    if votation_snapshot_path.exists():
        items.append((votation_snapshot_path, "votation_snapshot", votation_snapshot_url))
    for doc in downloaded:
        fp = Path(doc.file_path)
        if fp.exists():
            items.append((fp, doc.kind, doc.source_url))

    if not items:
        return

    deduped_items: list[tuple[Path, str, str]] = []
    seen_paths: set[str] = set()
    for path, kind, source_url in items:
        key = str(path.resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped_items.append((path, kind, source_url))

    families: dict[str, list[tuple[Path, str, str]]] = {}
    for item in deduped_items:
        families.setdefault(_kind_family(item[1]), []).append(item)

    try:
        con = _get_db_connection()
    except Exception as err:
        print(f"[WARN] Connexion SQLite impossible : {err} ; insertion ignorée.")
        return

    upserted_sources = 0
    linked_documents = 0
    try:
        for family in sorted(families.keys()):
            entry = _build_source_entry_from_family(
                votation_id=votation_id,
                family=family,
                items=families[family],
            )
            if entry is None:
                continue
            result = _db_upsert_source(con, entry)
            if result.get("action") == "error":
                print(f"[WARN] Insertion SQLite ignorée pour {family}: {result.get('reason', 'erreur inconnue')}")
                continue
            upserted_sources += 1
            linked_documents += int(result.get("documents_count") or 0)

        print(
            f"[INFO] {upserted_sources} source(s) insérée(s)/mise(s) à jour dans SQLite "
            f"({linked_documents} document(s) lié(s))."
        )
    except Exception as err:
        print(f"[WARN] Erreur lors de l'insertion en base : {err}")
    finally:
        con.close()





def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Swissvotes official sources for one votation id")
    parser.add_argument("--votation-id", type=int, required=True, help="Swissvotes votation id (ex: 119, 639)")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Root output directory")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show planned operations without downloading")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    vote_url = BASE_URL.format(votation_id=args.votation_id)
    out_dir = args.output_root / f"votation_{args.votation_id}"
    md_path = out_dir / f"votation_{args.votation_id}.md"

    if args.dry_run:
        print(f"[DRY-RUN] Vote URL: {vote_url}")
        print(f"[DRY-RUN] Output dir: {out_dir}")
        print(f"[DRY-RUN] Markdown path: {md_path}")
        print("[DRY-RUN] HTML files are not persisted.")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    html_bytes, vote_effective_url = _fetch_prefer_french_page(vote_url, timeout_seconds=args.timeout)
    html_text = html_bytes.decode("utf-8", errors="replace")

    parser = _TextAndLinksParser()
    parser.feed(html_text)

    unique_links = _extract_unique_links(parser.links, vote_url)
    md_path.write_text(_render_markdown(vote_effective_url, html_text, args.votation_id), encoding="utf-8")

    chrono_url, message_url, debate_url, voting_text_url, results_by_domain_url = _extract_official_links_from_html(
        html_text,
        vote_url,
    )
    if (
        chrono_url is None
        or message_url is None
        or debate_url is None
        or voting_text_url is None
        or results_by_domain_url is None
    ):
        (
            fallback_chrono,
            fallback_message,
            fallback_debate,
            fallback_voting_text,
            fallback_results_by_domain,
        ) = _extract_official_links_fallback(unique_links)
        chrono_url = chrono_url or fallback_chrono
        message_url = message_url or fallback_message
        debate_url = debate_url or fallback_debate
        voting_text_url = voting_text_url or fallback_voting_text
        results_by_domain_url = results_by_domain_url or fallback_results_by_domain

    downloaded: list[DownloadedDocument] = []

    if chrono_url:
        try:
            chrono_payload, chrono_effective_url = _fetch_url_with_final_url(chrono_url, timeout_seconds=args.timeout)
            chrono_payload, chrono_effective_url = _resolve_french_alternate_page(
                initial_url=chrono_effective_url,
                initial_payload=chrono_payload,
                timeout_seconds=args.timeout,
            )
            # Le HTML de chronologie est un document de travail: ne pas le stocker sur disque.
            # En revanche, pour une source non HTML (ex: PDF), on conserve le binaire.
            if _is_html_like_url(chrono_effective_url):
                for stale_name in ("chronologie_officielle.html", "chronologie_officielle.htm"):
                    stale_path = out_dir / stale_name
                    if stale_path.exists():
                        stale_path.unlink()
            else:
                chrono_path = _download_document(
                    chrono_effective_url,
                    out_dir,
                    "chronologie_officielle",
                    timeout_seconds=args.timeout,
                    payload=chrono_payload,
                )
                downloaded.append(
                    DownloadedDocument(
                        kind="chronologie_officielle",
                        source_url=chrono_effective_url,
                        file_path=str(chrono_path),
                    )
                )

            chrono_md_path = _write_chronology_markdown(
                source_url=chrono_effective_url,
                raw_payload=chrono_payload,
                destination_dir=out_dir,
                votation_id=args.votation_id,
            )
            downloaded.append(
                DownloadedDocument(
                    kind="chronologie_officielle_markdown",
                    source_url=chrono_effective_url,
                    file_path=str(chrono_md_path),
                )
            )
        except OSError as chrono_err:
            existing_md = out_dir / "chronologie_officielle.md"
            if existing_md.exists():
                print(f"[WARN] Chronologie inaccessible ({chrono_err}); version existante conservée: {existing_md}")
                downloaded.append(
                    DownloadedDocument(
                        kind="chronologie_officielle_markdown",
                        source_url=chrono_url,
                        file_path=str(existing_md),
                    )
                )
            else:
                print(f"[WARN] Chronologie inaccessible ({chrono_err}); aucun fichier existant.")

    if message_url:
        message_path = _download_document(
            message_url,
            out_dir,
            "message_conseil_federal",
            timeout_seconds=args.timeout,
        )
        downloaded.append(
            DownloadedDocument(
                kind="message_conseil_federal",
                source_url=message_url,
                file_path=str(message_path),
            )
        )

    if debate_url:
        debate_path = _download_document(
            debate_url,
            out_dir,
            "debat_parlementaire",
            timeout_seconds=args.timeout,
        )
        downloaded.append(
            DownloadedDocument(
                kind="debat_parlementaire",
                source_url=debate_url,
                file_path=str(debate_path),
            )
        )

    if voting_text_url:
        voting_text_path = _download_document(
            voting_text_url,
            out_dir,
            "texte_soumis_au_vote",
            timeout_seconds=args.timeout,
        )
        downloaded.append(
            DownloadedDocument(
                kind="texte_soumis_au_vote",
                source_url=voting_text_url,
                file_path=str(voting_text_path),
            )
        )

    if results_by_domain_url:
        results_by_domain_path = _download_document(
            results_by_domain_url,
            out_dir,
            "resultats_par_domaine",
            timeout_seconds=args.timeout,
        )
        downloaded.append(
            DownloadedDocument(
                kind="resultats_par_domaine",
                source_url=results_by_domain_url,
                file_path=str(results_by_domain_path),
            )
        )

    _upsert_all_downloaded_in_db(
        downloaded=downloaded,
        votation_snapshot_path=md_path,
        votation_snapshot_url=vote_effective_url,
        votation_id=args.votation_id,
    )

    summary = {
        "votation_id": args.votation_id,
        "vote_url": vote_url,
        "output_dir": str(out_dir),
        "markdown_file": str(md_path),
        "downloaded_documents": [asdict(item) for item in downloaded],
        "missing_documents": [
            name
            for name, url in (
                ("chronologie_officielle", chrono_url),
                ("message_conseil_federal", message_url),
                ("debat_parlementaire", debate_url),
                ("texte_soumis_au_vote", voting_text_url),
                ("resultats_par_domaine", results_by_domain_url),
            )
            if not url
        ],
        "timestamp": datetime.now().isoformat(),
    }

    summary_path = out_dir / f"votation_{args.votation_id}_download_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


