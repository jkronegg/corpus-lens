#!/usr/bin/env python3
"""Télécharge un article Wikipedia et l'exporte en Markdown."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable, cast
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_LANG = "fr"
DEFAULT_OUT_DIR = Path("sources/wikipedia")
REPO_ROOT = Path(__file__).resolve().parents[4]
DB_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
DB_MODULE_PATH = DB_SCRIPTS_DIR / "db.py"
get_db_connection = None
register_source_document = None
try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_wikipedia", DB_MODULE_PATH)
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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
API_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"
PAGE_TEMPLATE = "https://{lang}.wikipedia.org/wiki/{title}"
ARCHIVE_DOMAINS = (
    "web.archive.org",
    "archive.today",
    "archive.is",
    "archive.ph",
    "archive.vn",
    "archive.wikiwix.com",
    "perma.cc",
)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "article"


def yaml_escape(value: str) -> str:
    return (value or "").replace('"', "'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Télécharge un article Wikipedia en Markdown.")
    parser.add_argument("--title", required=True, help="Titre Wikipedia de l'article")
    parser.add_argument("--lang", default=DEFAULT_LANG, help="Code langue Wikipedia, défaut: fr")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Dossier de sortie Markdown")
    parser.add_argument("--dry-run", action="store_true", help="Vérifie l'article sans écrire de fichier")
    return parser.parse_args()


def build_page_url(title: str, lang: str) -> str:
    return PAGE_TEMPLATE.format(lang=lang, title=quote(title.replace(" ", "_")))


def build_api_url(lang: str) -> str:
    return API_TEMPLATE.format(lang=lang)


def fetch_article_html(title: str, lang: str) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    params = {
        "action": "parse",
        "page": title,
        "prop": "text|sections|displaytitle",
        "format": "json",
        "formatversion": 2,
        "redirects": 1,
    }
    response = session.get(build_api_url(lang), params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise ValueError(data["error"].get("info", "Erreur Wikipedia inconnue"))

    parse = data.get("parse")
    if not parse:
        raise ValueError("Article Wikipedia introuvable")

    html = parse.get("text", "")
    display_title = parse.get("displaytitle") or title
    page_name = parse.get("title") or title
    page_url = build_page_url(page_name, lang)
    return {
        "html": html,
        "display_title": display_title,
        "page_title": page_name,
        "page_url": page_url,
        "api_url": response.url,
    }


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_reference_text(text: str) -> str:
    """Supprime les symboles de renvoi Wikipedia (↑, †, guillemets, espaces) en début de libellé."""
    # ↑ U+2191, ↓ U+2193, † U+2020, ‡ U+2021, guillemets simples/doubles, espaces
    text = re.sub(r"^[\u2191\u2192\u2193\u2020\u2021\u00ab\u00bb\u2018\u2019\u201c\u201d'\"\s]+", "", text or "")
    return text.strip()


def normalize_image_url(url: str, lang: str) -> str:
    """Normalise une URL d'image Wikipedia (absolue, relative ou sans schéma)."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith("/"):
        return f"https://{lang}.wikipedia.org{raw}"
    # Cas API rencontré: upload.wikimedia.org/... (sans schéma)
    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", raw, flags=re.IGNORECASE):
        return "https://" + raw
    return urljoin(f"https://{lang}.wikipedia.org/", raw)


def is_wikipedia_family_url(url: str) -> bool:
    """Retourne True si l'URL pointe vers Wikipedia/Wikimedia."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host.endswith("wikipedia.org") or host.endswith("wikimedia.org")


def build_wikiwix_archive_url(url: str) -> str:
    """Construit l'URL d'archive Wikiwix pour une URL cible."""
    return f"https://archive.wikiwix.com/cache/?url={quote(url, safe='')}"


def is_archive_url(url: str) -> bool:
    """Retourne True si l'URL pointe vers un service d'archive connu."""
    host = (urlparse(url).hostname or "").lower()
    return any(host.endswith(domain) for domain in ARCHIVE_DOMAINS)


def build_reference_number_map(root: Tag) -> dict[str, int]:
    """Construit un mapping id de référence -> numéro d'affichage."""
    mapping: dict[str, int] = {}
    for item in root.select("ol.references > li[id], ul.references > li[id]"):
        ref_id = (item.get("id") or "").strip()
        if ref_id and ref_id not in mapping:
            mapping[ref_id] = len(mapping) + 1
    return mapping


def resolve_reference_number(href: str, reference_numbers: dict[str, int] | None = None) -> int | None:
    """Résout un numéro de référence à partir d'un href de type #cite_note-* ou URL#cite_note-*."""
    if not href or not reference_numbers:
        return None
    parsed = urlparse(href)
    fragment = (parsed.fragment or "").strip()
    if not fragment and href.startswith("#"):
        fragment = href[1:].strip()
    if not fragment:
        return None
    return reference_numbers.get(fragment)


def download_image(image_url: str, images_dir: Path, markdown_image_prefix: str, lang: str) -> str | None:
    """Télécharge une image et retourne son chemin relatif Markdown, ou None en cas d'erreur."""
    try:
        image_url = normalize_image_url(image_url, lang)
        if not image_url:
            return None

        response = requests.get(image_url, timeout=20, headers={"User-Agent": USER_AGENT})
        if response.status_code != 200:
            return None

        # Générer un nom de fichier unique basé sur l'URL
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
        parsed_url = urlparse(image_url)
        filename = Path(parsed_url.path).name or f"image_{url_hash}"

        # Créer le sous-répertoire d'images propre au document s'il n'existe pas.
        images_dir.mkdir(parents=True, exist_ok=True)

        filepath = images_dir / filename
        filepath.write_bytes(response.content)

        # Retourner le chemin relatif attendu depuis le Markdown.
        return f"{markdown_image_prefix}/{filename}"
    except Exception as exc:
        print(f"[WARN] Impossible de télécharger {image_url}: {exc}")
        return None


def extract_and_download_images(html: str, output_dir: Path, lang: str, document_key: str) -> dict[str, str]:
    """Extrait les images du HTML et les télécharge. Retourne un mapping URL -> chemin local."""
    soup = BeautifulSoup(html or "", "html.parser")
    images_mapping = {}
    safe_document_key = slugify(document_key)
    images_dir = output_dir / "images" / safe_document_key
    markdown_image_prefix = f"images/{safe_document_key}"

    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src:
            continue

        full_url = normalize_image_url(src, lang)
        if not full_url:
            continue

        # Ne télécharger que si pas déjà fait
        if full_url not in images_mapping:
            local_path = download_image(full_url, images_dir, markdown_image_prefix, lang)
            if local_path:
                images_mapping[full_url] = local_path
                images_mapping[src] = local_path  # Mapper aussi l'URL originale

    return images_mapping


def inline_text(node: Any, images_mapping: dict[str, str] | None = None) -> str:
    if images_mapping is None:
        images_mapping = {}
    
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    if node.name in {"sup", "style", "script", "table"}:
        return ""
    if node.name == "br":
        return "\n"
    if node.name in {"a", "span", "b", "strong", "i", "em", "small", "code"}:
        return "".join(inline_text(child, images_mapping) for child in node.children)
    if node.name == "img":
        src = node.get("src", "").strip()
        alt = node.get("alt", "").strip()

        # Chercher le chemin local de l'image
        if src in images_mapping:
            local_path = images_mapping[src]
            return f"![{alt}]({local_path})"
        elif alt:
            return f"![{alt}]"
        return ""
    return "".join(inline_text(child, images_mapping) for child in node.children)


def inline_markdown(
    node: Any,
    images_mapping: dict[str, str] | None = None,
    reference_numbers: dict[str, int] | None = None,
) -> str:
    """Convertit un nœud inline en Markdown en conservant les liens."""
    if images_mapping is None:
        images_mapping = {}

    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    if node.name in {"style", "script", "table"}:
        return ""
    if node.name == "sup":
        links: list[str] = []
        for anchor in node.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            num = resolve_reference_number(href, reference_numbers)
            if num is not None:
                links.append(f"[{num}](#ref-{num})")
        if links:
            return "".join(links)
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "a":
        label = _clean_text(
            "".join(inline_markdown(child, images_mapping, reference_numbers) for child in node.children)
        )
        href = (node.get("href") or "").strip()
        if not label:
            return ""
        if not href:
            return label
        ref_num = resolve_reference_number(href, reference_numbers)
        if ref_num is not None:
            return f"[{ref_num}](#ref-{ref_num})"
        fragment = (urlparse(href).fragment or "").strip()
        if fragment.startswith("cite_ref-"):
            return ""
        url = normalize_image_url(href, DEFAULT_LANG)
        if url.startswith(("http://", "https://")):
            md_link = f"[{label}]({url})"
            if not is_wikipedia_family_url(url) and not is_archive_url(url):
                archive_url = build_wikiwix_archive_url(url)
                md_link = f"{md_link} ([archive]({archive_url}))"
            return md_link
        return label
    if node.name in {"span", "b", "strong", "i", "em", "small", "code"}:
        return "".join(inline_markdown(child, images_mapping, reference_numbers) for child in node.children)
    if node.name == "img":
        src = node.get("src", "").strip()
        alt = node.get("alt", "").strip()
        if src in images_mapping:
            return f"![{alt}]({images_mapping[src]})"
        return f"![{alt}]" if alt else ""

    return "".join(inline_markdown(child, images_mapping, reference_numbers) for child in node.children)


def table_to_markdown(table: Tag, images_mapping: dict[str, str] | None = None) -> list[str]:
    if images_mapping is None:
        images_mapping = {}

    rows = []
    for tr in table.find_all("tr", recursive=True):
        cells = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            cells.append(_clean_text(inline_text(cell, images_mapping)))
        if cells:
            rows.append(cells)
    if not rows:
        return []

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = []
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * width) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def references_to_markdown(
    node: Tag,
    images_mapping: dict[str, str] | None = None,
    reference_numbers: dict[str, int] | None = None,
) -> list[str]:
    """Convertit les références Wikipedia (mw-references-wrap / ol.references) en liste Markdown."""
    if images_mapping is None:
        images_mapping = {}

    lines: list[str] = []
    reference_items = node.select("ol.references > li, ul.references > li")
    for item in reference_items:
        ref_id = (item.get("id") or "").strip()
        ref_num = reference_numbers.get(ref_id) if reference_numbers else None
        if ref_num is None:
            ref_num = len(lines) + 1

        text = _clean_reference_text(_clean_text(inline_markdown(item, images_mapping, reference_numbers)))
        archive_links: list[str] = []

        # Conserver aussi les liens d'archive, même s'ils ne sont pas visibles dans le texte inline.
        for anchor in item.select("a[href]"):
            href = normalize_image_url((anchor.get("href") or "").strip(), DEFAULT_LANG)
            if not href:
                continue
            href_l = href.lower()
            if not any(domain in href_l for domain in ARCHIVE_DOMAINS):
                continue

            label = _clean_text(inline_text(anchor, images_mapping)) or "archive"
            md_link = f"[{label}]({href})"
            if md_link not in archive_links and md_link not in text:
                archive_links.append(md_link)

        if archive_links:
            text = text.rstrip()
            suffix = ", ".join(archive_links)
            text = f"{text} (archives: {suffix})" if text else f"archives: {suffix}"

        if text:
            lines.append(f"{ref_num}. <a id=\"ref-{ref_num}\"></a> {text}")

    if lines:
        lines.append("")
    return lines


def html_to_markdown(html: str, images_mapping: dict[str, str] | None = None) -> str:
    if images_mapping is None:
        images_mapping = {}

    soup = BeautifulSoup(html or "", "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    reference_numbers = build_reference_number_map(root)
    lines: list[str] = []

    def process_children(parent: Tag) -> None:
        for child in parent.children:
            if isinstance(child, NavigableString) or not isinstance(child, Tag):
                continue

            if child.name == "section":
                process_children(child)
                continue

            if child.name in {"h2", "h3", "h4"}:
                level = int(child.name[1])
                headline = child.select_one(".mw-headline")
                heading = _clean_text(inline_text(headline, images_mapping) if headline else inline_text(child, images_mapping))
                if heading:
                    lines.append(f"{'#' * level} {heading}")
                    lines.append("")
                continue

            if child.name == "p":
                text = _clean_text(inline_markdown(child, images_mapping, reference_numbers))
                if text:
                    lines.append(text)
                    lines.append("")
                continue

            if child.name == "div":
                class_names = set(child.get("class", []))
                if "mw-references-wrap" in class_names or child.select_one("ol.references, ul.references"):
                    ref_lines = references_to_markdown(child, images_mapping, reference_numbers)
                    if ref_lines:
                        lines.extend(ref_lines)
                        continue

            if child.name in {"ul", "ol"}:
                for li in child.find_all("li", recursive=False):
                    text = _clean_text(inline_markdown(li, images_mapping, reference_numbers))
                    if text:
                        lines.append(f"- {text}")
                lines.append("")
                continue

            if child.name == "blockquote":
                text = _clean_text(inline_markdown(child, images_mapping, reference_numbers))
                if text:
                    for part in text.split("\n"):
                        lines.append(f"> {part.strip()}".rstrip())
                    lines.append("")
                continue

            if child.name == "figure":
                caption = child.find("figcaption")
                caption_text = _clean_text(inline_text(caption, images_mapping)) if caption else ""
                img = child.find("img")
                if img:
                    img_src = img.get("src", "").strip()
                    img_alt = img.get("alt", "").strip()
                    if img_src in images_mapping:
                        lines.append(f"![{img_alt}]({images_mapping[img_src]})")
                        if caption_text:
                            lines.append(f"*{caption_text}*")
                        lines.append("")
                        continue
                if caption_text:
                    lines.append(f"*{caption_text}*")
                    lines.append("")
                continue

            if child.name == "table":
                lines.extend(table_to_markdown(child, images_mapping))
                lines.append("")
                continue

            process_children(child)

    process_children(root)

    # Clean up extra blank lines
    cleaned: list[str] = []
    for line in lines:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned) + "\n"


def build_markdown(title: str, lang: str, article: dict[str, Any], body_md: str) -> str:
    now = dt.datetime.now().isoformat(timespec="seconds")
    display_title = re.sub(r"<[^>]+>", "", str(article.get("display_title") or title)).strip() or title
    page_url = article["page_url"]
    api_url = article["api_url"]
    lines = [
        "---",
        f'title: "{yaml_escape(display_title)}"',
        f'date_consultation: "{now}"',
        f'url: "{yaml_escape(page_url)}"',
        'transformation_by: "skill fetch-wikipedia-article"',
        f'language_distribution: "{lang}:100"',
        "---",
        "",
        "## Page 1",
        "",
        f"# {display_title}",
        "",
    ]
    if body_md.strip():
        lines.append(body_md.strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def register_output_in_db(output_path: Path, article: dict[str, Any], lang: str, image_paths: list[Path]) -> None:
    if not DB_AVAILABLE:
        return
    if get_db_connection is None or register_source_document is None:
        return
    db_connect = cast(Callable[[], Any], get_db_connection)
    register_source = cast(Callable[..., dict[str, Any]], register_source_document)

    page_title = str(article.get("page_title") or "").strip() or output_path.stem
    display_title = re.sub(r"<[^>]+>", "", str(article.get("display_title") or page_title)).strip() or page_title
    page_url = str(article.get("page_url") or "").strip()
    try:
        con = db_connect()
    except Exception as exc:
        print(f"[WARN] SQLite indisponible pour {output_path.name}: {exc}")
        return

    try:
        result = register_source(
            con,
            origin_path=output_path,
            identifiant_source=f"SRC-WIKIPEDIA-{slugify(page_title).upper()}-{lang.upper()}",
            titre=display_title,
            url=page_url,
            auteurs=["Wikipedia"],
            langues=lang,
            type_source="secondaire",
            nombre_pages=1,
            categorie="autre",
            ner_status=1,
        )
        if result.get("action") == "error":
            print(f"[WARN] Insertion SQLite ignorée pour {output_path.name}: {result.get('reason', 'erreur inconnue')}")
            return

        for image_path in image_paths:
            derived_result = register_source(
                con,
                origin_path=image_path,
                parent_path=output_path,
                ner_status=0,
            )
            if derived_result.get("action") == "error":
                print(
                    f"[WARN] Insertion SQLite ignorée pour {image_path.name}: "
                    f"{derived_result.get('reason', 'erreur inconnue')}"
                )
    finally:
        con.close()


def main() -> int:
    args = parse_args()

    try:
        article = fetch_article_html(args.title, args.lang)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "query": args.title,
                    "found": False,
                    "message": str(exc),
                    "lang": args.lang,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    output_name = f"wikipedia_{slugify(article['page_title'])}_{args.lang}.md"
    output_path = args.out_dir / output_name

    if args.dry_run:
        print(
            json.dumps(
                {
                    "query": args.title,
                    "found": True,
                    "title": article["page_title"],
                    "output": str(output_path),
                    "url": article["page_url"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    # Créer le dossier de sortie et télécharger les images dans un sous-répertoire dédié au document.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    images_mapping = extract_and_download_images(article["html"], args.out_dir, args.lang, output_path.stem)

    body_md = html_to_markdown(article["html"], images_mapping)
    markdown = build_markdown(args.title, args.lang, article, body_md)
    write_output(output_path, markdown)
    register_output_in_db(
        output_path,
        article,
        args.lang,
        [args.out_dir / rel_path for rel_path in sorted(set(images_mapping.values()))],
    )

    print(
        json.dumps(
            {
                "query": args.title,
                "found": True,
                "title": article["page_title"],
                "output": str(output_path),
                "url": article["page_url"],
                "images_downloaded": len(images_mapping),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


