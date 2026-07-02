import argparse
import csv
import string
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = "https://elitessuisses.unil.ch/indexPersonnes.php?l=a"
DEFAULT_OUT_DIR = Path(r"C:\Users\Julien\git\kronegg\histoire_suisse\sortie")
HEADERS = ["nom", "prénom", "dates", "mandats", "Projet", "URL"]


def extract_rows(page):
    return page.eval_on_selector_all(
        "table tbody tr",
        """
        rows => rows.map(r => {
          const tds = Array.from(r.querySelectorAll('td'));
          if (tds.length < 5) return null;

          const cleanText = (el) => (el?.innerText || '').trim().replace(/\\s+/g, ' ');
          const firstHref = (...cells) => {
            for (const cell of cells) {
              const a = cell?.querySelector('a[href]');
              if (a) {
                try {
                  return new URL(a.getAttribute('href'), window.location.href).href;
                } catch (_) {
                  return a.href || '';
                }
              }
            }
            return '';
          };

          const imgNames = [];
          for (const img of Array.from(tds[4].querySelectorAll('img[src]'))) {
            const src = img.getAttribute('src') || '';
            const file = src.split('/').pop() || src;
            const name = file.replace(/\\.[^.]+$/, '').trim();
            if (name && !imgNames.includes(name)) imgNames.push(name);
          }

          return [
            cleanText(tds[0]),
            cleanText(tds[1]),
            cleanText(tds[2]),
            cleanText(tds[3]),
            imgNames.join(', '),
            firstHref(tds[0], tds[1])
          ];
        }).filter(Boolean)
        """,
    )


def export_letter(page, letter, out_path):
    page.locator(".btn-alpha", has_text=letter).first.click(timeout=15000)
    page.wait_for_timeout(1500)
    rows = extract_rows(page)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Export CSV des personnes EliteSuisses via CDP.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--letters", default=string.ascii_uppercase)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--out-a", default="elitessuisses_personnes_A.csv")
    parser.add_argument("--out-all", default="elitessuisses_personnes_A_Z.csv")
    args = parser.parse_args()

    letters = "".join(ch for ch in args.letters.upper() if ch in string.ascii_uppercase)
    if not letters:
        raise SystemExit("Aucune lettre valide dans --letters (utiliser A-Z).")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_a = out_dir / args.out_a
    out_all = out_dir / args.out_all

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        rows_a = export_letter(page, "A", out_a)

        all_rows = []
        for letter in letters:
            page.locator(".btn-alpha", has_text=letter).first.click(timeout=15000)
            page.wait_for_timeout(1500)
            rows = extract_rows(page)
            all_rows.extend(rows)
            print(f"{letter}: {len(rows)} lignes")

        with out_all.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)
            writer.writerows(all_rows)

        print(f"Fichier A: {out_a} ({len(rows_a)} lignes)")
        print(f"Fichier {letters}: {out_all} ({len(all_rows)} lignes)")
        page.close()


if __name__ == "__main__":
    main()

