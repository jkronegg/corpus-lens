#!/usr/bin/env python3
"""Télécharge l'index Dodis des personnes et remplit assets/persons.csv via CDP.

python -u "C:\path_to_project\.agents\skills\fetch-dodis-person-details\assets\fetch_dodis_persons_csv.py" --wait-ms 200

Log de progression : C:/path_to_project/.agents/skills/fetch-dodis-person-details/assets/fetch_dodis_persons_csv.full.out.log
CSV cible : C:/path_to_project/.agents/skills/fetch-dodis-person-details/assets/persons.csv
State file (reprise) : C:/path_to_project/.agents/skills/fetch-dodis-person-details/assets/fetch_dodis_persons_state.json

"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

SEARCH_URL = "https://dodis.ch/search?q=&c=Person&f=All&t=all&cb=doc"
BASE_URL = "https://dodis.ch"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DEFAULT_WAIT_MS = 1200
CSV_HEADERS = ["prénom", "nom", "année de naissance", "année de décès", "URL"]


def parse_args() -> argparse.Namespace:
    assets_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Construit assets/persons.csv depuis Dodis (catégorie Person).")
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL, help="Endpoint CDP, ex: http://127.0.0.1:9222")
    parser.add_argument("--url", default=SEARCH_URL, help="URL de recherche Dodis Person")
    parser.add_argument("--out-csv", type=Path, default=assets_dir / "persons.csv", help="Fichier CSV de sortie")
    parser.add_argument(
        "--state-file",
        type=Path,
        default=assets_dir / "fetch_dodis_persons_state.json",
        help="Fichier d'état pour reprise après échec",
    )
    parser.add_argument("--wait-ms", type=int, default=DEFAULT_WAIT_MS, help="Attente après navigation/clic pagination")
    parser.add_argument("--max-pages", type=int, default=0, help="Limite de pages (0 = toutes)")
    parser.add_argument("--reset-state", action="store_true", help="Ignore/supprime l'état existant et repart de la première page")
    return parser.parse_args()


def parse_given_and_years(value: str) -> tuple[str, str, str]:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if not text:
        return "", "", ""

    m = re.match(r"^(.*?)(?:\(([^)]*)\))?$", text)
    if not m:
        return text, "", ""

    first_name = (m.group(1) or "").strip()
    years_raw = (m.group(2) or "").strip()
    years = re.findall(r"\d{4}", years_raw)

    birth = years[0] if len(years) >= 1 else ""
    death = years[1] if len(years) >= 2 else ""
    return first_name, birth, death


def extract_rows(page) -> list[dict[str, str]]:
    raw_rows = page.eval_on_selector_all(
        "table.searchResult tr",
        """
        rows => rows.slice(1).map(row => {
          const tds = Array.from(row.querySelectorAll('td'));
          if (tds.length < 2) return null;
          const a = tds[0].querySelector('a[href]') || tds[1].querySelector('a[href]');
          return {
            col1: (tds[0].innerText || '').trim(),
            col2: (tds[1].innerText || '').trim(),
            href: a ? a.getAttribute('href') : ''
          };
        }).filter(Boolean)
        """,
    )

    parsed: list[dict[str, str]] = []
    for row in raw_rows:
        last_name = re.sub(r"\s+", " ", (row.get("col1") or "")).strip()
        first_name, birth, death = parse_given_and_years(row.get("col2") or "")
        href = (row.get("href") or "").strip()
        url = urljoin(BASE_URL, href) if href else ""

        parsed.append(
            {
                "prénom": first_name,
                "nom": last_name,
                "année de naissance": birth,
                "année de décès": death,
                "URL": url,
            }
        )

    return parsed


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_key(row: dict[str, str]) -> str:
    return row.get("URL") or f"{row.get('nom')}|{row.get('prénom')}|{row.get('année de naissance')}|{row.get('année de décès')}"


def load_existing_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def scrape_all_pages(
    page,
    search_url: str,
    wait_ms: int,
    max_pages: int,
    out_csv: Path,
    state_file: Path,
    reset_state: bool,
) -> tuple[list[dict[str, str]], int]:
    existing_rows = load_existing_rows(out_csv)
    all_rows: list[dict[str, str]] = list(existing_rows)
    seen_urls: set[str] = {dedupe_key(r) for r in existing_rows}

    if reset_state and state_file.exists():
        state_file.unlink()

    state = load_state(state_file)
    can_resume = (
        not reset_state
        and state.get("search_url") == search_url
        and isinstance(state.get("last_completed_page"), int)
        and state.get("next_page_url")
    )

    if can_resume:
        page.goto(state["next_page_url"], wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(wait_ms)
        current_page = int(state["last_completed_page"]) + 1
    else:
        current_page = 1

    while True:
        page.wait_for_selector("table.searchResult", timeout=120000)
        page.wait_for_timeout(wait_ms)

        rows = extract_rows(page)
        added = 0
        for row in rows:
            key = dedupe_key(row)
            if key in seen_urls:
                continue
            seen_urls.add(key)
            all_rows.append(row)
            added += 1

        print(f"Page {current_page}: {len(rows)} lignes extraites, {added} nouvelles")

        next_page_num = current_page + 1
        next_link = page.locator("div.pagination a", has_text=str(next_page_num)).first
        next_page_url = ""
        if next_link.count() > 0:
            href = (next_link.get_attribute("href") or "").strip()
            next_page_url = urljoin(page.url, href) if href else ""

        write_csv(out_csv, all_rows)
        save_state(
            state_file,
            {
                "search_url": search_url,
                "last_completed_page": current_page,
                "next_page_url": next_page_url,
                "rows_written": len(all_rows),
                "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
            },
        )

        if max_pages > 0 and current_page >= max_pages:
            break

        if next_link.count() == 0:
            break

        next_link.click(timeout=20000)
        page.wait_for_timeout(wait_ms)

        current_page = next_page_num

    return all_rows, current_page


def main() -> int:
    args = parse_args()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(args.wait_ms)

        rows, last_page = scrape_all_pages(
            page,
            search_url=args.url,
            wait_ms=args.wait_ms,
            max_pages=args.max_pages,
            out_csv=args.out_csv,
            state_file=args.state_file,
            reset_state=args.reset_state,
        )
        page.close()

    print(
        json.dumps(
            {
                "pages_limit": args.max_pages,
                "last_page_processed": last_page,
                "rows_written": len(rows),
                "output": str(args.out_csv),
                "state_file": str(args.state_file),
                "search_url": args.url,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

