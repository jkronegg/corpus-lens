#!/usr/bin/env python3
"""Search Dodis and extract all results across all pages.

This skill performs a Dodis search and extracts all result rows with complete
metadata (Date, N°, Type, Sujet, Résumé, Langue, URL) from each page.
Results are exported to JSON and Markdown formats.

Usage:
  python scripts/dodis_fetch_results.py --url "https://dodis.ch/search?q=1935&c=Document&f=All&t=all&cb=doc"
  python scripts/dodis_fetch_results.py --url "https://dodis.ch/search?q=1935&c=Document&f=All&t=all&cb=doc" --headful
  python scripts/dodis_fetch_results.py --url "https://dodis.ch/search?q=1935&c=Document&f=All&t=all&cb=doc" --pause-on-challenge
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Iterable
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

DEFAULT_OUTPUT_DIR = Path("sources/dodis")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BLOCK_MARKERS = (
    "making sure you're not a bot",
    "making sure you&#39;re not a bot",
    "oh noes",
    "within.website",
    "access denied",
    "anubis",
)


@dataclass
class SearchResult:
    """A single search result row from Dodis."""
    date: Optional[str] = None
    number: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    url: Optional[str] = None


@dataclass
class PageResults:
    """Results from a single search results page."""
    page_index: int
    page_url: str
    blocked: bool
    items: list[SearchResult] = field(default_factory=list)
    error: Optional[str] = None


def _is_blocked(title: str, html: str) -> bool:
    """Check if page is blocked by anti-bot detection."""
    blob = f"{title}\n{html}".lower()
    if any(marker in blob for marker in BLOCK_MARKERS):
        return True
    # Defensive: if page is nearly empty, consider it non-exploitable
    return len(_norm_ws(blob)) < 40


def _norm_ws(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def _normalize_full_date(text: str) -> str:
    """Normalize full dates to dd.MM.yyyy, keep non-full dates unchanged."""
    value = _norm_ws(text)
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    if not match:
        return value
    day, month, year = match.groups()
    return f"{int(day):02d}.{int(month):02d}.{year}"


def _wait_for_results_or_state(page, timeout_ms: int = 12000) -> None:
    """Wait until Dodis results table, no-results block, or challenge state is visible."""
    try:
        page.wait_for_function(
            """
            () => {
              const hasResults = document.querySelectorAll('table.searchResult tbody tr.document_list').length > 0;
              const noResults = !!document.querySelector('#no_results');
              const body = (document.body?.innerText || '').toLowerCase();
              const blocked = body.includes("making sure you're not a bot") ||
                              body.includes("making sure you\u0026#39;re not a bot") ||
                              body.includes('oh noes') ||
                              body.includes('within.website') ||
                              body.includes('access denied') ||
                              body.includes('anubis');
              return hasResults || noResults || blocked;
            }
            """,
            timeout=timeout_ms,
        )
    except Exception:
        # Best effort wait: page may still be usable even if the condition was not met in time.
        pass


def _extract_table_rows(page) -> list[SearchResult]:
    """Extract all rows from the search results table."""
    results: list[SearchResult] = []
    try:
        rows_data = page.evaluate(
            """
            () => {
              const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
              const rows = Array.from(document.querySelectorAll('table.searchResult tbody tr.document_list'));
              return rows.map((row) => {
                const tds = Array.from(row.querySelectorAll('td'));
                const values = tds.map((td) => norm(td.textContent || ''));

                let href = '';
                for (const a of Array.from(row.querySelectorAll('a[href]'))) {
                  const h = (a.getAttribute('href') || '').trim();
                  if (/^\\/\\d+$/.test(h)) {
                    href = h;
                    break;
                  }
                }

                return { values, href };
              });
            }
            """
        )

        for row in rows_data:
            values = row.get("values") or []
            if len(values) < 6:
                continue

            href = (row.get("href") or "").strip()
            abs_url = urljoin(page.url, href) if href else ""

            result = SearchResult(
                date=_normalize_full_date(values[1]) if len(values) > 1 else None,
                number=values[2] if len(values) > 2 else None,
                type=values[3] if len(values) > 3 else None,
                subject=values[4] if len(values) > 4 else None,
                summary=values[5] if len(values) > 5 else None,
                language=values[6] if len(values) > 6 else None,
                url=abs_url,
            )
            results.append(result)
    except Exception:
        pass

    return results


def _click_next_page(page) -> bool:
    """Try to find and click the 'next page' link."""
    # Dodis pagination is in .pagination and uses '>' for next page.
    # Navigating directly by href is more robust than UI click in headful sessions.
    locator = page.locator(".pagination a")
    try:
        for i in range(locator.count()):
            a = locator.nth(i)
            text = _norm_ws(a.inner_text(timeout=1000))
            href = (a.get_attribute("href") or "").strip()
            if text == ">" and href and href != "#":
                page.goto(urljoin(page.url, href), wait_until="domcontentloaded", timeout=90000)
                return True
    except Exception:
        pass
    return False


def _collect(url: str, max_pages: int, headful: bool, pause_on_challenge: bool, wait_time: float) -> list[PageResults]:
    """Collect search results from all pages."""
    collected: list[PageResults] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT)
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(int(wait_time * 1000))
        _wait_for_results_or_state(page)

        visited_urls: set[str] = set()

        for page_index in range(1, max_pages + 1):
            title = ""
            html = ""
            blocked = False
            items = []
            error = None

            try:
                # Get page content
                for _ in range(3):
                    try:
                        _wait_for_results_or_state(page)
                        title = page.title()
                        html = page.content()
                        break
                    except Exception:
                        page.wait_for_timeout(600)

                blocked = _is_blocked(title, html)
                if not blocked:
                    h1 = _norm_ws(page.locator("h1").first.inner_text(timeout=500) if page.locator("h1").count() else "")
                    if h1.lower() == "oh noes!":
                        blocked = True

                if blocked and pause_on_challenge and headful:
                    print("[INFO] Challenge detecte. Resolvez-le dans la fenetre, puis appuyez sur Entree...")
                    input()
                    page.wait_for_timeout(2500)
                    title = page.title()
                    html = page.content()
                    blocked = _is_blocked(title, html)

                if not blocked:
                    items = _extract_table_rows(page)

            except Exception as e:
                error = str(e)

            collected.append(
                PageResults(
                    page_index=page_index,
                    page_url=page.url,
                    blocked=blocked,
                    items=items,
                    error=error,
                )
            )

            if blocked:
                break

            if page.url in visited_urls:
                break
            visited_urls.add(page.url)

            # Try to navigate to next page before processing
            moved = _click_next_page(page)
            if not moved:
                break

            try:
                page.wait_for_load_state("domcontentloaded", timeout=90000)
            except Exception:
                pass
            page.wait_for_timeout(int(wait_time * 1000))
            _wait_for_results_or_state(page)

        context.close()
        browser.close()

    return collected


def _dedupe(items: Iterable[SearchResult]) -> list[SearchResult]:
    """Deduplicate results by URL."""
    out: list[SearchResult] = []
    seen: set[str] = set()
    for item in items:
        key = (item.url or "").lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(item)
    return out


def _extract_query_from_url(url: str) -> str:
    """Extract search query from URL."""
    parsed = urlparse(url)
    params = {}
    if parsed.query:
        for param in parsed.query.split("&"):
            if "=" in param:
                k, v = param.split("=", 1)
                params[k] = v
    return params.get("q", "search")


def _md_cell(text: Optional[str]) -> str:
    """Escape a Markdown table cell while preserving full content."""
    value = _norm_ws(text or "")
    return value.replace("|", "\\|")


def _render_markdown(url: str, pages: list[PageResults]) -> str:
    """Render results as Markdown."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_items = _dedupe(item for p in pages for item in p.items)
    query = _extract_query_from_url(url)

    lines: list[str] = [
        "# Recherche Dodis",
        "",
        f"- Requête: `{query}`",
        f"- URL de recherche: [lien](`{url}`)",
        f"- Date de consultation: `{now}`",
        f"- Pages visitées: `{len(pages)}`",
        f"- Résultats uniques collectés: `{len(all_items)}`",
        "",
        "## Résumé global",
        "",
    ]

    if not all_items:
        lines.append("Aucun résultat exploitable n'a été extrait automatiquement.")
    else:
        lines.append(f"Total: **{len(all_items)}** résultats")
        lines.append("")
        lines.append("| Date | N° | Type | Sujet | Résumé | Langue | URL |")
        lines.append("|------|-----|------|-------|--------|--------|-----|")

        for item in all_items:
            date_str = _md_cell(item.date)
            num_str = _md_cell(item.number)
            type_str = _md_cell(item.type)
            subject_str = _md_cell(item.subject)
            summary_str = _md_cell(item.summary)
            lang_str = _md_cell(item.language)
            url_str = f"[Lien]({item.url})" if item.url else ""

            lines.append(f"| {date_str} | {num_str} | {type_str} | {subject_str} | {summary_str} | {lang_str} | {url_str} |")

    lines.append("")
    lines.append("## Détails par page")
    lines.append("")

    for p in pages:
        lines.append(f"### Page {p.page_index}")
        lines.append("")
        lines.append(f"- URL: `{p.page_url}`")
        lines.append(f"- Statut anti-bot: `{'bloqué' if p.blocked else 'ok'}`")
        if p.error:
            lines.append(f"- Erreur: `{p.error}`")
        lines.append(f"- Nombre de résultats extraits: `{len(p.items)}`")
        lines.append("")

        if p.items:
            lines.append("| Date | N° | Type | Sujet | Résumé | Langue | URL |")
            lines.append("|------|-----|------|-------|--------|--------|-----|")
            for item in p.items:
                date_str = _md_cell(item.date)
                num_str = _md_cell(item.number)
                type_str = _md_cell(item.type)
                subject_str = _md_cell(item.subject)
                summary_str = _md_cell(item.summary)
                lang_str = _md_cell(item.language)
                url_str = f"[Lien]({item.url})" if item.url else ""
                lines.append(f"| {date_str} | {num_str} | {type_str} | {subject_str} | {summary_str} | {lang_str} | {url_str} |")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Dodis and extract all results")
    parser.add_argument("--url", required=True, help="Dodis search URL")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages to process")
    parser.add_argument("--headful", action="store_true", help="Launch browser visible")
    parser.add_argument("--wait-time", type=float, default=3.5, help="Wait time after page load")
    parser.add_argument("--pause-on-challenge", action="store_true", help="Pause on anti-bot challenge")
    parser.add_argument("--dry-run", action="store_true", help="Don't process, just show what would happen")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.dry_run:
        print(f"[DRY-RUN] Would search: {args.url}")
        print(f"[DRY-RUN] Output directory: {args.output_dir}")
        print(f"[DRY-RUN] Max pages: {args.max_pages}")
        return 0

    pages = _collect(
        url=args.url,
        max_pages=args.max_pages,
        headful=args.headful,
        pause_on_challenge=args.pause_on_challenge,
        wait_time=args.wait_time,
    )

    # Prepare all results
    all_results = _dedupe(item for p in pages for item in p.items)

    # Generate output filenames
    query = _extract_query_from_url(args.url)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_filename = f"dodis_{query}_{timestamp}.json"
    md_filename = f"dodis_{query}_{timestamp}.md"

    json_path = args.output_dir / json_filename
    md_path = args.output_dir / md_filename

    # Prepare JSON output
    json_data = {
        "search_url": args.url,
        "query": query,
        "date_consultation": dt.datetime.now().isoformat(),
        "pages_processed": len(pages),
        "total_results": len(all_results),
        "results": [asdict(r) for r in all_results],
    }

    # Write JSON
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write Markdown
    md = _render_markdown(args.url, pages)
    md_path.write_text(md, encoding="utf-8")

    # Print summary
    blocked = any(p.blocked for p in pages)
    print(json.dumps({
        "pages_processed": len(pages),
        "total_results": len(all_results),
        "json_output": str(json_path),
        "markdown_output": str(md_path),
        "anti_bot_detected": blocked,
        "timestamp": dt.datetime.now().isoformat(),
    }, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


