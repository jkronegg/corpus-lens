#!/usr/bin/env python3
"""
Histogramme de la vitesse de récolte des signatures pour les initiatives.

Vitesse = signatures valides déposées / nombre de jours entre
`dat-start` et `dat-submit`.

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_vitesse_recolte_initiatives.py"
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_vitesse_recolte_initiatives.py" --bins 10
"""

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "sources" / "swissvotes" / "histogramme_vitesse_recolte_signatures_initiatives.md"


@dataclass
class InitiativeSpeed:
    anr: str
    titre: str
    dat_start: str
    dat_submit: str
    signatures_valides: float
    jours_recolte: int
    vitesse: float


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


def _build_front_matter(source_path: Path) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    source_rel = source_path.as_posix()
    return [
        "---",
        'title: "Histogramme — vitesse de récolte des signatures (initiatives)"',
        f'date_publication: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
        f'  - "{source_rel}"',
        "---",
        "",
    ]


def _render_markdown(
    records_trimmed: list[InitiativeSpeed],
    bins_count: int,
    source_rel: Path,
    excluded_rows: int,
    low_extremes: list[InitiativeSpeed],
    high_extremes: list[InitiativeSpeed],
    total_valid_before_trim: int,
) -> str:
    speeds_sorted = sorted(r.vitesse for r in records_trimmed)
    n = len(speeds_sorted)
    mn = speeds_sorted[0]
    mx = speeds_sorted[-1]
    mean = sum(speeds_sorted) / n
    median = speeds_sorted[n // 2] if n % 2 == 1 else (speeds_sorted[n // 2 - 1] + speeds_sorted[n // 2]) / 2
    stddev = math.sqrt(sum((v - mean) ** 2 for v in speeds_sorted) / n)

    bins = _compute_bins(speeds_sorted, bins_count)
    max_count = max(c for _, _, c in bins)

    lines = _build_front_matter(source_rel)
    lines += [
        "# Histogramme — vitesse de récolte des signatures (initiatives populaires)",
        "",
        "**Variable analysée** : vitesse = `unter_g / (dat-submit - dat-start)` en signatures valides par jour.",
        "",
        "**Population** : initiatives populaires fédérales (`rechtsform = 3`) avec `dat-start`, `dat-submit` et `unter_g` valides.",
        "",
        "## Statistiques descriptives",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| N (initiatives valides, avant retrait des extrêmes) | {total_valid_before_trim} |",
        f"| N (initiatives utilisées pour l'histogramme) | {n} |",
        f"| Minimum | {mn:.1f} signatures/jour |",
        f"| Maximum | {mx:.1f} signatures/jour |",
        f"| Moyenne | {mean:.1f} signatures/jour |",
        f"| Médiane | {median:.1f} signatures/jour |",
        f"| Écart-type | {stddev:.1f} signatures/jour |",
        "",
        f"## Histogramme ({bins_count} intervalles)",
        "",
        "```text",
        f"{'Intervalle (sig./jour)':<30} {'N':>5}",
    ]

    for lo, hi, count in bins:
        label = f"[{lo:>8.1f} - {hi:>8.1f}["
        lines.append(f"{label:<30} {count:>5}  {_ascii_bar(count, max_count)}")

    lines += [
        "```",
        "",
        "## Tableau des intervalles",
        "",
        "| Intervalle (signatures/jour) | Nombre d'initiatives | % |",
        "|---|---:|---:|",
    ]

    for lo, hi, count in bins:
        pct = count / n * 100
        lines.append(f"| [{lo:.1f} - {hi:.1f}[ | {count} | {pct:.1f} % |")

    lines += [
        "",
        "## Notes méthodologiques",
        "",
        "- Le nombre de jours est calculé entre `dat-start` et `dat-submit`.",
        "- Les lignes avec date manquante/invalide, durée non positive, ou signatures manquantes sont exclues.",
        f"- Lignes exclues (qualité des données) : {excluded_rows}.",
        f"- Extrêmes retirés pour l'histogramme : {len(low_extremes)} plus faibles + {len(high_extremes)} plus élevées.",
        "",
    ]

    lines += [
        "## Traçabilité des extrêmes retirés",
        "",
        "| Côté | ANR | Titre | Début | Dépôt | Jours | Signatures valides | Vitesse (sig./jour) |",
        "|---|---:|---|---|---|---:|---:|---:|",
    ]

    for item in low_extremes:
        lines.append(
            f"| Bas 1% | {item.anr} | {item.titre} | {item.dat_start} | {item.dat_submit} | {item.jours_recolte} | {item.signatures_valides:.0f} | {item.vitesse:.1f} |"
        )

    for item in high_extremes:
        lines.append(
            f"| Haut 1% | {item.anr} | {item.titre} | {item.dat_start} | {item.dat_submit} | {item.jours_recolte} | {item.signatures_valides:.0f} | {item.vitesse:.1f} |"
        )

    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit l'histogramme de vitesse de récolte des signatures pour les initiatives."
    )
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV, help="Chemin du CSV Swissvotes")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="Fichier Markdown de sortie")
    parser.add_argument("--bins", type=int, default=10, help="Nombre de bins de l'histogramme")
    args = parser.parse_args()

    if args.bins < 1:
        raise SystemExit("[ERREUR] --bins doit être >= 1")
    if not args.csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.csv}")

    records: list[InitiativeSpeed] = []
    excluded_rows = 0

    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            start = _parse_date(row.get("dat-start", ""))
            submit = _parse_date(row.get("dat-submit", ""))
            signatures = _parse_number(row.get("unter_g", ""))

            if not start or not submit or signatures is None:
                excluded_rows += 1
                continue

            days = (submit - start).days
            if days <= 0 or signatures <= 0:
                excluded_rows += 1
                continue

            speed = signatures / days
            records.append(
                InitiativeSpeed(
                    anr=(row.get("anr", "") or "").strip(),
                    titre=(row.get("titel_kurz_f", "") or row.get("titel_kurz_d", "") or "").strip(),
                    dat_start=(row.get("dat-start", "") or "").strip(),
                    dat_submit=(row.get("dat-submit", "") or "").strip(),
                    signatures_valides=signatures,
                    jours_recolte=days,
                    vitesse=speed,
                )
            )

    if not records:
        raise SystemExit("[ERREUR] Aucune vitesse valide calculable dans le CSV.")

    records_sorted = sorted(records, key=lambda r: r.vitesse)
    total_valid_before_trim = len(records_sorted)

    trim_each_side = max(1, int(round(total_valid_before_trim * 0.01))) if total_valid_before_trim >= 3 else 0
    max_trim = (total_valid_before_trim - 1) // 2
    trim_each_side = min(trim_each_side, max_trim)

    low_extremes = records_sorted[:trim_each_side]
    high_extremes = records_sorted[-trim_each_side:] if trim_each_side > 0 else []
    records_trimmed = records_sorted[trim_each_side: total_valid_before_trim - trim_each_side] if trim_each_side > 0 else records_sorted

    if not records_trimmed:
        raise SystemExit("[ERREUR] Retrait des extrêmes trop agressif; aucun enregistrement restant.")

    try:
        source_rel = args.csv.resolve().relative_to(_PROJECT_ROOT.resolve())
    except ValueError:
        source_rel = args.csv.resolve()

    output_text = _render_markdown(
        records_trimmed,
        args.bins,
        source_rel,
        excluded_rows,
        low_extremes,
        high_extremes,
        total_valid_before_trim,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {args.output}")
    trimmed_speeds = [r.vitesse for r in records_trimmed]
    print(
        f"[INFO] N_total={total_valid_before_trim} | N_hist={len(records_trimmed)} | "
        f"trim_bas={len(low_extremes)} | trim_haut={len(high_extremes)} | "
        f"min_hist={min(trimmed_speeds):.1f} | max_hist={max(trimmed_speeds):.1f} | exclues={excluded_rows}"
    )


if __name__ == "__main__":
    main()

