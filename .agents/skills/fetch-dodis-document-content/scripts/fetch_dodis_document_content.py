#!/usr/bin/env python3
"""Télécharge le contenu d'un document Dodis et l'exporte en Markdown."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import mimetypes
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SKILL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[4]
DB_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
_DB_MODULE_PATH = DB_SCRIPTS_DIR / "db.py"
_DETECT_LANG_PATH = REPO_ROOT / ".agents" / "skills" / "translate-markdown" / "scripts" / "detect_markdown_language.py"
get_db_connection = None
register_source_document = None
try:
    spec = importlib.util.spec_from_file_location("named_entities_db_for_dodis_document", _DB_MODULE_PATH)
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

    module_name = "detect_markdown_language_shared_for_dodis_document"
    spec = importlib.util.spec_from_file_location(module_name, _DETECT_LANG_PATH)
    if spec is None or spec.loader is None:
        return None, None

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, "detect_language_distribution", None), getattr(module, "format_distribution", None)


_detect_language_distribution, _format_distribution = _load_language_detection_functions()

DEFAULT_OUT_DIR = Path("sources/dodis/documents")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DOCUMENT_URL_TEMPLATE = "https://dodis.ch/{document_id}?lang=fr"
EXCLUDED_IMAGE_BASENAMES = {
    "slider_off.svg",
    "twitter.png",
    "facebook-app-logo.png",
    "pin_0.png",
    "pdf-icon-small.png",
    "transcription.png",
}
SECTION_TITLES_FALLBACK = {
    "ancfct": "Fonctions",
    "ancwd": "Documents rédigés",
    "ancsd": "Documents signés",
    "ancmd": "Mentionné dans les documents",
    "ancac": "Destinataire d'une copie",
    "ancrd": "Documents reçus",
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    return normalized


def slugify(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "document"


def yaml_escape(value: str) -> str:
    return (value or "").replace('"', "'")


def _compute_language_distribution(text: str) -> str:
    if callable(_detect_language_distribution) and callable(_format_distribution):
        detected = _detect_language_distribution(text)
        return _format_distribution(detected)
    return "unknown:100"


def normalize_document_id(raw: str) -> str:
    document_id = re.sub(r"\s+", "", (raw or "").strip())
    if not document_id or not document_id.isdigit():
        raise ValueError("L'identifiant Dodis doit contenir uniquement des chiffres.")
    return document_id


def build_document_url(document_id: str) -> str:
    return DOCUMENT_URL_TEMPLATE.format(document_id=document_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Télécharge le contenu d'un document Dodis identifié par son numéro"
    )
    parser.add_argument("--document-id", required=True, help="Identifiant numérique Dodis (ex: 43445)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _slug_for_file(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "").strip())
    slug = re.sub(r"_+", "_", slug).strip("._")
    return slug or "image"


def _sanitize_md_cell(value: str) -> str:
    return _norm_ws(value).replace("|", "\\|")


def _build_markdown_table(headers: list[str], rows: list[dict[str, object]]) -> list[str]:
    clean_headers = [_sanitize_md_cell(h) or "-" for h in headers]
    if not clean_headers:
        clean_headers = ["Colonne 1"]

    has_url = any(_norm_ws(str(row.get("url") or "")) for row in rows)
    if has_url and "URL" not in clean_headers:
        clean_headers.append("URL")

    lines = [
        "| " + " | ".join(clean_headers) + " |",
        "| " + " | ".join("---" for _ in clean_headers) + " |",
    ]

    for row in rows:
        cells = [str(c) for c in (row.get("cells") or [])]
        values: list[str] = []
        for idx in range(len(clean_headers)):
            if has_url and idx == len(clean_headers) - 1 and clean_headers[idx] == "URL":
                row_url = _norm_ws(str(row.get("url") or ""))
                values.append(f"[Lien]({row_url})" if row_url else "")
                continue
            values.append(_sanitize_md_cell(cells[idx]) if idx < len(cells) else "")

        lines.append("| " + " | ".join(values) + " |")

    return lines


def _canonical_section_title(section: dict[str, object], index: int) -> str:
    raw_title = _norm_ws(str(section.get("title") or ""))
    if raw_title:
        return raw_title

    section_id = _norm_ws(str(section.get("id") or "")).lower()
    if section_id in SECTION_TITLES_FALLBACK:
        return SECTION_TITLES_FALLBACK[section_id]

    return f"Section {index}"


def _append_image_markdown(lines: list[str], image: dict[str, str]) -> None:
    local_rel = _sanitize_md_cell(image.get("markdown_path") or "")
    if not local_rel:
        return
    alt_text = _sanitize_md_cell(image.get("alt") or "Image Dodis") or "Image Dodis"
    source_url = _norm_ws(image.get("url") or "")
    lines.append(f"![{alt_text}]({local_rel})")
    if source_url:
        lines.append("")
        lines.append(f"Source: [Lien]({source_url})")
    lines.append("")


def _extract_extension_from_url_or_type(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
        return suffix

    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip())
    if guessed in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}:
        return guessed
    return ".bin"


def extract_page(page, url: str) -> dict[str, object]:
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(2500)

    title = page.title().strip()
    payload = page.evaluate(
        r"""
        () => {
          const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
          const text = norm(document.body?.innerText || '');
          const images = [];
          const seenImg = new Set();

          const sections = [];
          const sectionById = new Map();
          const rootBlocks = [];
          let currentSection = null;

          const getSection = (node) => {
            const id = norm(node.getAttribute('id') || '').toLowerCase();
            if (!id) return null;
            if (!sectionById.has(id)) {
              const section = {
                id,
                title: norm(node.textContent || ''),
                tables: [],
                blocks: [],
              };
              sectionById.set(id, section);
              sections.push(section);
            }
            return sectionById.get(id);
          };

          const extractTable = (table) => {
            const out = { headers: [], rows: [] };
            const headerCells = Array.from(table.querySelectorAll('thead th'));
            if (headerCells.length) {
              out.headers = headerCells.map((th) => norm(th.textContent || ''));
            }

            const bodyRows = table.tBodies.length
              ? Array.from(table.tBodies).flatMap((tb) => Array.from(tb.rows))
              : Array.from(table.querySelectorAll('tr'));

            for (const tr of bodyRows) {
              const cellNodes = Array.from(tr.querySelectorAll('td'));
              if (!cellNodes.length) {
                if (!out.headers.length) {
                  const thCells = Array.from(tr.querySelectorAll('th')).map((th) => norm(th.textContent || ''));
                  if (thCells.length) {
                    out.headers = thCells;
                  }
                }
                continue;
              }

              const cells = cellNodes.map((td) => norm(td.textContent || ''));
              let rowUrl = '';
              for (const a of Array.from(tr.querySelectorAll('a[href]'))) {
                const href = norm(a.getAttribute('href') || '');
                if (!href) continue;
                try {
                  const absHref = new URL(href, window.location.href).href;
                  if (/\/\d+$/.test(new URL(absHref).pathname)) {
                    rowUrl = absHref;
                    break;
                  }
                  if (!rowUrl) {
                    rowUrl = absHref;
                  }
                } catch (_) {
                }
              }

              out.rows.push({ cells, url: rowUrl });
            }

            if (!out.headers.length && out.rows.length) {
              const first = out.rows[0];
              const firstCells = Array.isArray(first.cells) ? first.cells : [];
              const looksLikeHeader =
                !first.url &&
                firstCells.length >= 2 &&
                firstCells.every((cell) => !!norm(cell));
              if (looksLikeHeader) {
                out.headers = firstCells;
                out.rows = out.rows.slice(1);
              }
            }

            return out;
          };

          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
          let currentNode = walker.currentNode;
          while (currentNode) {
            if (
              currentNode.tagName === 'STRONG' &&
              /^anc/i.test(currentNode.getAttribute('id') || '')
            ) {
              currentSection = getSection(currentNode);
            } else if (currentNode.tagName === 'TABLE') {
              const tableData = extractTable(currentNode);
              if (currentSection) {
                const tableIndex = currentSection.tables.push(tableData) - 1;
                currentSection.blocks.push({ kind: 'table', table_index: tableIndex });
              }
            } else if (currentNode.tagName === 'IMG') {
              const src = norm(currentNode.getAttribute('src') || '');
              if (src && !src.startsWith('data:')) {
                let abs = '';
                try {
                  abs = new URL(src, window.location.href).href;
                } catch (_) {
                  abs = '';
                }

                if (abs && !seenImg.has(abs)) {
                  seenImg.add(abs);
                  const imageInfo = {
                    url: abs,
                    alt: norm(currentNode.getAttribute('alt') || ''),
                  };
                  images.push(imageInfo);

                  if (currentSection) {
                    currentSection.blocks.push({ kind: 'image', url: abs });
                  } else {
                    rootBlocks.push({ kind: 'image', url: abs });
                  }
                }
              }
            }
            currentNode = walker.nextNode();
          }

          return { text, images, sections, rootBlocks };
        }
        """,
    )

    return {
        "title": title,
        "text": str(payload.get("text") or ""),
        "image_urls": [img for img in (payload.get("images") or []) if isinstance(img, dict)],
        "sections": [sec for sec in (payload.get("sections") or []) if isinstance(sec, dict)],
        "root_blocks": [b for b in (payload.get("rootBlocks") or []) if isinstance(b, dict)],
    }


def guess_output_name(document_id: str) -> str:
    return f"dodis_document_{slugify(document_id)}.md"


def download_images(page, output_markdown_path: Path, images: list[dict[str, str]]) -> list[dict[str, str]]:
    if not images:
        return []

    image_dir = output_markdown_path.parent / f"{output_markdown_path.stem}_images"
    image_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for index, image in enumerate(images, start=1):
        url = _norm_ws(str(image.get("url") or ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        source_basename = Path(urlparse(url).path).name.lower()
        if source_basename in EXCLUDED_IMAGE_BASENAMES:
            continue

        try:
            response = page.context.request.get(url, timeout=120000)
        except Exception as exc:
            print(f"[WARN] Téléchargement image échoué ({url}): {exc}")
            continue

        if not response.ok:
            print(f"[WARN] Image non téléchargée ({url}): HTTP {response.status}")
            continue

        content = response.body()
        if not content:
            continue

        content_type = response.headers.get("content-type", "")
        ext = _extract_extension_from_url_or_type(url, content_type)
        parsed_name = Path(urlparse(url).path).name
        base = _slug_for_file(Path(parsed_name).stem if parsed_name else f"image_{index:03d}")
        file_name = f"{index:03d}_{base}{ext}"
        image_path = image_dir / file_name
        image_path.write_bytes(content)

        downloaded.append(
            {
                "url": url,
                "alt": _norm_ws(str(image.get("alt") or "")),
                "path": str(image_path),
                "markdown_path": f"{image_dir.name}/{image_path.name}",
            }
        )

    return downloaded


def build_markdown(
    document_id: str,
    source_url: str,
    page_title: str,
    page_text: str,
    sections: list[dict[str, object]],
    root_blocks: list[dict[str, object]],
    downloaded_images: list[dict[str, str]],
) -> str:
    now = dt.datetime.now().isoformat(timespec="seconds")
    title = page_title or f"Document Dodis {document_id}"
    language_distribution = _compute_language_distribution(page_text)

    lines = [
        "---",
        f'title: "{yaml_escape(title)}"',
        f'date_consultation: "{now}"',
        f'url: "{yaml_escape(source_url)}"',
        f'document_id: "{yaml_escape(document_id)}"',
        f'language_distribution: "{yaml_escape(language_distribution)}"',
        'transformation_by: "skill fetch-dodis-document-content"',
        "---",
        "",
        "## Page 1",
        "",
        f"# {title}",
        "",
        f"- Identifiant Dodis: {document_id}",
        f"- URL: {source_url}",
        "",
        "## Contenu Dodis structuré",
        "",
    ]

    if page_text:
        lines.append("### Texte brut")
        lines.append("")
        lines.append(page_text)
        lines.append("")

    downloaded_by_url = {
        _norm_ws(str(image.get("url") or "")): image
        for image in downloaded_images
        if _norm_ws(str(image.get("url") or ""))
    }

    if root_blocks:
        rendered_root = False
        for block in root_blocks:
            if str(block.get("kind") or "") != "image":
                continue
            image = downloaded_by_url.get(_norm_ws(str(block.get("url") or "")))
            if image is None:
                continue
            if not rendered_root:
                lines.append("### Illustrations générales")
                lines.append("")
            rendered_root = True
            _append_image_markdown(lines, image)

    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        title_label = _canonical_section_title(section, index)
        tables = section.get("tables") if isinstance(section.get("tables"), list) else []
        blocks = section.get("blocks") if isinstance(section.get("blocks"), list) else []

        lines.append(f"### {title_label}")
        lines.append("")

        rendered_any_content = False

        if blocks:
            for block in blocks:
                kind = str(block.get("kind") or "")
                if kind == "image":
                    image = downloaded_by_url.get(_norm_ws(str(block.get("url") or "")))
                    if image is None:
                        continue
                    rendered_any_content = True
                    _append_image_markdown(lines, image)
                    continue

                if kind != "table":
                    continue

                try:
                    table_index = int(block.get("table_index"))
                except (TypeError, ValueError):
                    continue
                if table_index < 0 or table_index >= len(tables):
                    continue
                table = tables[table_index]
                if not isinstance(table, dict):
                    continue
                rows_list = table.get("rows") if isinstance(table.get("rows"), list) else []
                headers_list = [str(h) for h in (table.get("headers") if isinstance(table.get("headers"), list) else [])]
                if not rows_list:
                    continue

                rendered_any_content = True
                if not headers_list:
                    max_cols = max(len(r.get("cells") or []) for r in rows_list)
                    headers_list = [f"Colonne {i}" for i in range(1, max_cols + 1)]
                lines.extend(_build_markdown_table(headers_list, rows_list))
                lines.append("")
        else:
            for table_idx, table in enumerate(tables, start=1):
                if not isinstance(table, dict):
                    continue
                rows_list = table.get("rows") if isinstance(table.get("rows"), list) else []
                headers_list = [str(h) for h in (table.get("headers") if isinstance(table.get("headers"), list) else [])]
                if not rows_list:
                    continue

                rendered_any_content = True
                if not headers_list:
                    max_cols = max(len(r.get("cells") or []) for r in rows_list)
                    headers_list = [f"Colonne {i}" for i in range(1, max_cols + 1)]

                if len(tables) > 1:
                    lines.append(f"Tableau {table_idx}")
                    lines.append("")
                lines.extend(_build_markdown_table(headers_list, rows_list))
                lines.append("")

        if not rendered_any_content:
            lines.append("Aucun contenu extrait pour cette section.")
        lines.append("")

    return "\n".join(lines)


def register_output_in_db(
    output_path: Path,
    source_url: str,
    document_id: str,
    page_title: str,
    downloaded_images: list[dict[str, str]],
) -> None:
    if not DB_AVAILABLE:
        return

    parsed = urlparse(source_url)
    unique_part = parsed.path.rstrip("/").split("/")[-1] or document_id
    identifiant_source = f"SRC-DODIS-DOC-{slugify(document_id)}-{slugify(unique_part).upper()}"
    title = f"Dodis: Document {document_id}"

    try:
        con = get_db_connection()
    except Exception as exc:
        print(f"[WARN] SQLite indisponible pour {output_path.name}: {exc}")
        return

    try:
        result = register_source_document(
            con,
            origin_path=output_path,
            identifiant_source=identifiant_source,
            titre=title,
            url=source_url,
            auteurs=["Dodis"],
            pertinence=0.65,
            type_source="secondaire",
            lisible=True,
            nombre_pages=1,
            categorie="autre",
            ner_status=1,
        )
        if result.get("action") == "error":
            print(f"[WARN] Insertion SQLite ignorée pour {output_path.name}: {result.get('reason', 'erreur inconnue')}")
            return

        for image in downloaded_images:
            image_path = Path(image.get("path") or "")
            if not image_path.exists():
                continue
            image_result = register_source_document(
                con,
                origin_path=image_path,
                parent_path=output_path,
                author="skill fetch-dodis-document-content",
                ner_status=0,
            )
            if image_result.get("action") == "error":
                print(
                    f"[WARN] Image non indexée ({image_path.name}): "
                    f"{image_result.get('reason', 'erreur inconnue')}"
                )
    finally:
        con.close()


def main() -> int:
    args = parse_args()

    try:
        document_id = normalize_document_id(args.document_id)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "query": args.document_id,
                    "found": False,
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    source_url = build_document_url(document_id)
    output_path = args.out_dir / guess_output_name(document_id)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "query": document_id,
                    "found": True,
                    "url": source_url,
                    "output": str(output_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        extracted = extract_page(page, source_url)
        downloaded_images = download_images(
            page=page,
            output_markdown_path=output_path,
            images=[dict(item) for item in (extracted.get("image_urls") or [])],
        )
        page.close()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown(
        document_id=document_id,
        source_url=source_url,
        page_title=extracted.get("title", ""),
        page_text=extracted.get("text", ""),
        sections=[dict(item) for item in (extracted.get("sections") or [])],
        root_blocks=[dict(item) for item in (extracted.get("root_blocks") or [])],
        downloaded_images=downloaded_images,
    )
    output_path.write_text(markdown, encoding="utf-8")
    register_output_in_db(
        output_path,
        source_url,
        document_id,
        extracted.get("title", ""),
        downloaded_images,
    )

    print(
        json.dumps(
            {
                "query": document_id,
                "found": True,
                "url": source_url,
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


