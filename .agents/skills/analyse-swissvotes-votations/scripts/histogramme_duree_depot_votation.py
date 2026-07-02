#!/usr/bin/env python3
"""
Histogramme des durées entre dépôt d'une initiative et date de votation.

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_duree_depot_votation.py"
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_duree_depot_votation.py" --bins 10
"""

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "sources" / "swissvotes" / "histogramme_duree_depot_votation_initiatives.md"


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


def _ascii_bar(count: int, max_count: int, width: int = 40) -> str:
    if max_count <= 0:
        return ""
    bar_len = round(count / max_count * width)
    return "#" * bar_len


def _compute_bins(values: list[int], bins_count: int) -> list[tuple[float, float, int]]:
    mn = min(values)
    mx = max(values)

    if bins_count <= 1:
        return [(float(mn), float(mx), len(values))]

    if mn == mx:
        return [(float(mn), float(mx + 1), len(values))]

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


def _build_front_matter(title: str, source_path: Path) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    source_rel = source_path.as_posix()
    return [
        "---",
        f'title: "{_escape_yaml(title)}"',
        f'date_publication: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
        f'  - "{_escape_yaml(source_rel)}"',
        "---",
        "",
    ]


def build_markdown(days_list: list[int], bins_count: int, source_name: str) -> str:
    days_list = sorted(days_list)
    n = len(days_list)
    mn = days_list[0]
    mx = days_list[-1]
    mean = sum(days_list) / n
    median = days_list[n // 2] if n % 2 == 1 else (days_list[n // 2 - 1] + days_list[n // 2]) / 2
    stddev = math.sqrt(sum((d - mean) ** 2 for d in days_list) / n)

    bins = _compute_bins(days_list, bins_count)
    max_count = max(c for _, _, c in bins)

    lines = [
        "# Histogramme — durée entre le dépôt et la votation (initiatives populaires)",
        "",
        "**Variable analysée** : nombre de jours entre `dat-submit` (dépôt des signatures) et `datum` (date du scrutin).",
        "",
        "**Population** : initiatives populaires fédérales (`rechtsform = 3`) avec `dat-submit` et `datum` renseignés.",
        "",
        "## Statistiques descriptives",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| N (initiatives valides) | {n} |",
        f"| Minimum | {mn} jours ({mn/365.25:.1f} ans) |",
        f"| Maximum | {mx} jours ({mx/365.25:.1f} ans) |",
        f"| Moyenne | {mean:.0f} jours ({mean/365.25:.1f} ans) |",
        f"| Médiane | {median:.0f} jours ({median/365.25:.1f} ans) |",
        f"| Écart-type | {stddev:.0f} jours |",
        "",
        f"## Histogramme ({bins_count} intervalles)",
        "",
        "```text",
        f"{'Intervalle (jours)':<26} {'N':>5}",
    ]

    for lo, hi, count in bins:
        label = f"[{lo:>6.0f} - {hi:>6.0f}["
        lines.append(f"{label:<26} {count:>5}  {_ascii_bar(count, max_count)}")

    lines += [
        "```",
        "",
        "## Tableau des intervalles",
        "",
        "| Intervalle (jours) | Intervalle (années) | Nombre d'initiatives | % |",
        "|---|---|---:|---:|",
    ]

    for lo, hi, count in bins:
        pct = count / n * 100
        lo_y = lo / 365.25
        hi_y = hi / 365.25
        lines.append(f"| [{lo:.0f} - {hi:.0f}[ | [{lo_y:.1f} - {hi_y:.1f}[ | {count} | {pct:.1f} % |")

    lines += [
        "",
        "## Observations",
        "",
        (
            f"La durée médiane entre le dépôt d'une initiative et la votation est de **{median:.0f} jours** "
            f"({median/365.25:.1f} ans), pour une moyenne de **{mean:.0f} jours** ({mean/365.25:.1f} ans)."
        ),
        (
            f"La distribution s'étend de {mn} jours ({mn/365.25:.1f} an) à {mx} jours ({mx/365.25:.1f} ans), "
            f"avec un écart-type de {stddev:.0f} jours."
        ),
        "",
        "> **Note méthodologique** : les initiatives pour lesquelles `dat-submit` ou `datum` est absent, égal à `0` ou à `.` ont été exclues de l'analyse.",
        "",
    ]

    title = "Histogramme — durée entre le dépôt d'une initiative et la votation"
    front_matter = _build_front_matter(title, Path(source_name))
    return "\n".join(front_matter + lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit l'histogramme des durées entre dépôt d'initiative et votation."
    )
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV, help="Chemin du CSV Swissvotes")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="Fichier Markdown de sortie")
    parser.add_argument("--bins", type=int, default=10, help="Nombre de bins de l'histogramme")
    args = parser.parse_args()

    if args.bins < 1:
        raise SystemExit("[ERREUR] --bins doit être >= 1")
    if not args.csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.csv}")

    durations: list[int] = []
    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            submit = _parse_date(row.get("dat-submit", ""))
            vote = _parse_date(row.get("datum", ""))
            if not submit or not vote:
                continue

            days = (vote - submit).days
            if days >= 0:
                durations.append(days)

    if not durations:
        raise SystemExit("[ERREUR] Aucune durée valide calculable dans le CSV.")

    try:
        source_rel = args.csv.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        source_rel = args.csv.resolve()

    output_text = build_markdown(durations, args.bins, str(source_rel))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {args.output}")
    print(f"[INFO] N={len(durations)} | min={min(durations)} | max={max(durations)}")


if __name__ == "__main__":
    main()

