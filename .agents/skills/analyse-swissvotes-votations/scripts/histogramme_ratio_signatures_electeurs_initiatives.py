#!/usr/bin/env python3
"""
Histogramme du ratio signatures valides / signataires potentiels (Suisses 18+) pour les initiatives.

Ratio (%) = 100 * unter_g / suisses_18plus_interpolé

Le dénominateur est le nombre d'habitants suisses de 18 ans et plus, interpolé
linéairement à la date de fin de récolte des signatures (`dat-submit`) à partir
d'une série annuelle externe. Cela approche mieux le vivier de personnes ayant
le droit de signer une initiative.

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_ratio_signatures_electeurs_initiatives.py"
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_ratio_signatures_electeurs_initiatives.py" --bins 10
"""

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"
_DEFAULT_SWISS18_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-population-suisse" / "assets" / "habitants_suisses_18plus_par_annee.csv"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "sources" / "swissvotes" / "histogramme_ratio_signatures_electeurs_initiatives.md"


def _parse_date(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw or raw in (".", "0", "9999"):
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def _to_decimal_year(date_value: datetime) -> float:
    start = datetime(date_value.year, 1, 1)
    next_start = datetime(date_value.year + 1, 1, 1)
    year_len = (next_start - start).days
    if year_len <= 0:
        return float(date_value.year)
    day_idx = (date_value - start).days
    return date_value.year + (day_idx / year_len)


def _load_swiss_18plus_series(path: Path) -> list[tuple[float, float]]:
    """Charge la série annuelle (année, habitants suisses 18+) depuis le CSV d'analyse-population-suisse."""
    series: list[tuple[float, float]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year_raw = (row.get("annee") or "").strip()
            # Compatibilité avec les variantes de colonnes possibles.
            value_raw = (
                row.get("habitants_suisses_18plus_estimes")
                or row.get("habitants_suisses_18plus")
                or ""
            )
            value = _parse_number(value_raw)
            if not year_raw or value is None or value <= 0:
                continue
            try:
                year = int(year_raw)
            except ValueError:
                continue
            series.append((float(year), value))
    series.sort(key=lambda x: x[0])
    return series


def _interpolate_signer_pool(target_date: datetime, series: list[tuple[float, float]]) -> float | None:
    """Interpole linéairement les Suisses 18+ à la date cible, depuis une série annuelle triée."""
    if not series:
        return None
    target = _to_decimal_year(target_date)
    if target <= series[0][0]:
        return series[0][1]
    if target >= series[-1][0]:
        return series[-1][1]

    for i in range(len(series) - 1):
        d0, v0 = series[i]
        d1, v1 = series[i + 1]
        if d0 <= target <= d1:
            span = d1 - d0
            if span == 0:
                return v0
            t = (target - d0) / span
            return v0 + t * (v1 - v0)
    return series[-1][1]


def _parse_number(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw or raw in (".", "0", "9999"):
        return None
    raw = raw.replace("'", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _ascii_bar(count: int, max_count: int, width: int = 40) -> str:
    if max_count <= 0:
        return ""
    bar_len = round(count / max_count * width)
    return "#" * bar_len


def _compute_bins(values: list[float], bins_count: int) -> list[tuple[float, float, int]]:
    mn = min(values)
    mx = max(values)

    if bins_count <= 1:
        return [(mn, mx, len(values))]

    if mn == mx:
        return [(mn, mn + 1.0, len(values))]

    width = (mx - mn) / bins_count
    bins: list[tuple[float, float, int]] = []
    for i in range(bins_count):
        lo = mn + i * width
        hi = mn + (i + 1) * width
        count = sum(1 for v in values if v >= lo and (v < hi or i == bins_count - 1))
        bins.append((lo, hi, count))
    return bins


def _escape_yaml(value: str) -> str:
    return (value or "").replace('"', "'")


def _build_front_matter(source_path: Path) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    source_rel = source_path.as_posix()
    return [
        "---",
        'title: "Histogramme — ratio signatures valides / électeurs inscrits (initiatives)"',
        f'date_publication: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
        f'  - "{_escape_yaml(source_rel)}"',
        "---",
        "",
    ]


def build_markdown(
    ratios_pct: list[float],
    bins_count: int,
    source_name: str,
    swiss18_source_name: str,
    excluded_rows: int,
    series_n: int,
) -> str:
    ratios_pct = sorted(ratios_pct)
    n = len(ratios_pct)
    mn = ratios_pct[0]
    mx = ratios_pct[-1]
    mean = sum(ratios_pct) / n
    median = ratios_pct[n // 2] if n % 2 == 1 else (ratios_pct[n // 2 - 1] + ratios_pct[n // 2]) / 2
    stddev = math.sqrt(sum((v - mean) ** 2 for v in ratios_pct) / n)

    bins = _compute_bins(ratios_pct, bins_count)
    max_count = max(c for _, _, c in bins)

    lines = [
        "# Histogramme — ratio signatures valides / Suisses 18+ (initiatives populaires)",
        "",
        "**Variable analysée** : ratio = `100 * unter_g / suisses_18plus_interpolé` (en %).",
        "Le dénominateur est interpolé linéairement à la date de `dat-submit`.",
        "",
        "**Population** : initiatives populaires fédérales (`rechtsform = 3`) avec `unter_g` et `dat-submit` valides.",
        "",
        "## Statistiques descriptives",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| N (initiatives valides) | {n} |",
        f"| Minimum | {mn:.3f} % |",
        f"| Maximum | {mx:.3f} % |",
        f"| Moyenne | {mean:.3f} % |",
        f"| Médiane | {median:.3f} % |",
        f"| Écart-type | {stddev:.3f} points de % |",
        "",
        f"## Histogramme ({bins_count} intervalles)",
        "",
        "```text",
        f"{'Intervalle (%)':<24} {'N':>5}",
    ]

    for lo, hi, count in bins:
        label = f"[{lo:>7.3f} - {hi:>7.3f}["
        lines.append(f"{label:<24} {count:>5}  {_ascii_bar(count, max_count)}")

    lines += [
        "```",
        "",
        "## Tableau des intervalles",
        "",
        "| Intervalle (%) | Nombre d'initiatives | % |",
        "|---|---:|---:|",
    ]

    for lo, hi, count in bins:
        pct = count / n * 100
        lines.append(f"| [{lo:.3f} - {hi:.3f}[ | {count} | {pct:.1f} % |")

    lines += [
        "",
        "## Notes méthodologiques",
        "",
        "- Le ratio est calculé comme `100 * unter_g / suisses_18plus_interpolé`.",
        "- **Normalisation par signataires potentiels** : `suisses_18plus` est interpolé à `dat-submit` "
        f"  à partir d'une série annuelle de {series_n} points (source: `{swiss18_source_name}`).",
        "- Les lignes avec `unter_g`, `dat-submit` ou `suisses_18plus` manquant/invalide (`.`, `0`, `9999`) sont exclues.",
        "- Les lignes avec `suisses_18plus_interpolé <= 0` ou `unter_g <= 0` sont exclues.",
        f"- Lignes exclues (qualité des données) : {excluded_rows}.",
        "",
    ]

    title = "Histogramme — ratio signatures valides / Suisses 18+"
    front_matter = _build_front_matter(Path(source_name))
    front_matter[6:6] = [f'  - "{_escape_yaml(Path(swiss18_source_name).as_posix())}"']
    return "\n".join(front_matter + lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit l'histogramme du ratio signatures valides / électeurs inscrits pour les initiatives."
    )
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV, help="Chemin du CSV Swissvotes")
    parser.add_argument(
        "--swiss-18-csv",
        type=Path,
        default=_DEFAULT_SWISS18_CSV,
        help="CSV annuel des habitants suisses de 18+",
    )
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="Fichier Markdown de sortie")
    parser.add_argument("--bins", type=int, default=10, help="Nombre de bins de l'histogramme")
    args = parser.parse_args()

    if args.bins < 1:
        raise SystemExit("[ERREUR] --bins doit être >= 1")
    if not args.csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.csv}")
    if not args.swiss_18_csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.swiss_18_csv}")

    ratios_pct: list[float] = []
    excluded_rows = 0

    # --- Étape 1 : charger la série annuelle des Suisses 18+ ---
    signer_pool_series = _load_swiss_18plus_series(args.swiss_18_csv)
    if not signer_pool_series:
        raise SystemExit("[ERREUR] Aucun point valide trouvé dans le CSV des Suisses 18+.")

    # --- Étape 2 : calculer les ratios pour les initiatives ---
    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            signatures = _parse_number(row.get("unter_g", ""))
            submit_date = _parse_date(row.get("dat-submit", ""))

            if signatures is None or submit_date is None or signatures <= 0:
                excluded_rows += 1
                continue

            signer_pool_at_submit = _interpolate_signer_pool(submit_date, signer_pool_series)
            if signer_pool_at_submit is None or signer_pool_at_submit <= 0:
                excluded_rows += 1
                continue

            ratio_pct = 100.0 * signatures / signer_pool_at_submit
            ratios_pct.append(ratio_pct)

    if not ratios_pct:
        raise SystemExit("[ERREUR] Aucun ratio valide calculable dans le CSV.")

    try:
        source_rel = args.csv.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        source_rel = args.csv.resolve()

    try:
        swiss18_source_rel = args.swiss_18_csv.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        swiss18_source_rel = args.swiss_18_csv.resolve()

    output_text = build_markdown(
        ratios_pct,
        args.bins,
        str(source_rel),
        str(swiss18_source_rel),
        excluded_rows,
        len(signer_pool_series),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {args.output}")
    print(
        f"[INFO] N={len(ratios_pct)} | min={min(ratios_pct):.3f}% | max={max(ratios_pct):.3f}% | exclues={excluded_rows}"
    )


if __name__ == "__main__":
    main()

