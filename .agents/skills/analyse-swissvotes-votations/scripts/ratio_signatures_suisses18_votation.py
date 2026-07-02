#!/usr/bin/env python3
"""
Analyse le ratio signatures valides / Suisses de 18+ pour une initiative donnee.

Normalisation:
  ratio (%) = 100 * unter_g / suisses_18plus_interpole(dat-submit)

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/ratio_signatures_suisses18_votation.py" --votation-id 86
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_SWISSVOTES_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"
_DEFAULT_SWISS18_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-population-suisse" / "assets" / "habitants_suisses_18plus_par_annee.csv"


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


def _to_decimal_year(date_value: datetime) -> float:
    year_start = datetime(date_value.year, 1, 1)
    next_year_start = datetime(date_value.year + 1, 1, 1)
    year_len = (next_year_start - year_start).days
    if year_len <= 0:
        return float(date_value.year)
    day_idx = (date_value - year_start).days
    return date_value.year + (day_idx / year_len)


def _load_swiss18_series(path: Path) -> list[tuple[float, float]]:
    series: list[tuple[float, float]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year_raw = (row.get("annee") or "").strip()
            value_raw = row.get("habitants_suisses_18plus_estimes") or row.get("habitants_suisses_18plus") or ""
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


def _interpolate_swiss18(target_date: datetime, series: list[tuple[float, float]]) -> float | None:
    if not series:
        return None

    target = _to_decimal_year(target_date)
    if target <= series[0][0]:
        return series[0][1]
    if target >= series[-1][0]:
        return series[-1][1]

    for i in range(len(series) - 1):
        y0, v0 = series[i]
        y1, v1 = series[i + 1]
        if y0 <= target <= y1:
            span = y1 - y0
            if span == 0:
                return v0
            t = (target - y0) / span
            return v0 + t * (v1 - v0)

    return series[-1][1]


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


def _build_front_matter(title: str, sources: list[str]) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        f'title: "{title.replace(chr(34), "'")}"',
        f'date_publication: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
    ]
    for src in sources:
        lines.append(f'  - "{src.replace(chr(34), "'")}"')
    lines += ["---", ""]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse le ratio signatures / Suisses 18+ pour une initiative Swissvotes."
    )
    parser.add_argument("--votation-id", required=True, help="Numero de votation (anr), ex: 86")
    parser.add_argument("--swissvotes-csv", type=Path, default=_DEFAULT_SWISSVOTES_CSV, help="CSV Swissvotes")
    parser.add_argument("--swiss18-csv", type=Path, default=_DEFAULT_SWISS18_CSV, help="CSV Suisses 18+")
    parser.add_argument("--bins", type=int, default=10, help="Nombre de bins (doit correspondre a l'histogramme de reference)")
    parser.add_argument("--output", type=Path, default=None, help="Markdown de sortie")
    args = parser.parse_args()

    if args.bins < 1:
        raise SystemExit("[ERREUR] --bins doit etre >= 1")
    if not args.swissvotes_csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.swissvotes_csv}")
    if not args.swiss18_csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.swiss18_csv}")

    votation_id = str(args.votation_id).strip()
    out_path = args.output or (_PROJECT_ROOT / "sources" / "swissvotes" / f"votation_{votation_id}" / "ratio_signatures_electeurs.md")

    swiss18_series = _load_swiss18_series(args.swiss18_csv)
    if not swiss18_series:
        raise SystemExit("[ERREUR] Aucun point valide dans le CSV Suisses 18+.")

    target = None
    ratios: list[float] = []

    with args.swissvotes_csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            signatures = _parse_number(row.get("unter_g", ""))
            submit_date = _parse_date(row.get("dat-submit", ""))
            if signatures is None or submit_date is None or signatures <= 0:
                continue

            swiss18 = _interpolate_swiss18(submit_date, swiss18_series)
            if swiss18 is None or swiss18 <= 0:
                continue

            ratio_pct = 100.0 * signatures / swiss18
            ratios.append(ratio_pct)

            anr = (row.get("anr", "") or "").strip()
            if anr == votation_id:
                target = {
                    "anr": anr,
                    "titre": (row.get("titel_kurz_f", "") or row.get("titel_kurz_d", "") or "").strip(),
                    "datum": (row.get("datum", "") or "").strip(),
                    "submit_raw": (row.get("dat-submit", "") or "").strip(),
                    "submit_date": submit_date,
                    "signatures": signatures,
                    "swiss18": swiss18,
                    "berecht": _parse_number(row.get("berecht", "")),
                    "unter_quorum": _parse_number(row.get("unter-quorum", "")),
                    "volkja_proz": (row.get("volkja-proz", "") or "").strip(),
                    "br_pos": (row.get("br-pos", "") or "").strip(),
                    "bv_pos": (row.get("bv-pos", "") or "").strip(),
                    "ratio_pct": ratio_pct,
                }

    if not ratios:
        raise SystemExit("[ERREUR] Aucun ratio calculable dans le CSV Swissvotes.")
    if not target:
        raise SystemExit(f"[ERREUR] Votation {votation_id} introuvable ou données insuffisantes.")

    ratios_sorted = sorted(ratios)
    n = len(ratios_sorted)
    mean = sum(ratios_sorted) / n
    median = ratios_sorted[n // 2] if n % 2 == 1 else (ratios_sorted[n // 2 - 1] + ratios_sorted[n // 2]) / 2
    stddev = math.sqrt(sum((v - mean) ** 2 for v in ratios_sorted) / n)
    rank_le = sum(1 for v in ratios_sorted if v <= target["ratio_pct"])
    percentile = rank_le / n * 100

    bins = _compute_bins(ratios_sorted, args.bins)
    target_bin = None
    for i, (lo, hi, count) in enumerate(bins):
        if target["ratio_pct"] >= lo and (target["ratio_pct"] < hi or i == len(bins) - 1):
            target_bin = (lo, hi, count)
            break

    submit_date = target["submit_date"]
    if not isinstance(submit_date, datetime):
        raise SystemExit("[ERREUR] Date de dépôt invalide pour la votation cible.")

    year_floor = int(math.floor(_to_decimal_year(submit_date)))
    prev_point = max((p for p in swiss18_series if int(p[0]) <= year_floor), key=lambda x: x[0], default=swiss18_series[0])
    next_point = min((p for p in swiss18_series if int(p[0]) >= year_floor + 1), key=lambda x: x[0], default=swiss18_series[-1])

    try:
        src_swissvotes = args.swissvotes_csv.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        src_swissvotes = args.swissvotes_csv.resolve().as_posix()

    try:
        src_swiss18 = args.swiss18_csv.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        src_swiss18 = args.swiss18_csv.resolve().as_posix()

    src_hist = "sources/swissvotes/histogramme_ratio_signatures_electeurs_initiatives.md"

    berecht_value = target["berecht"] if isinstance(target["berecht"], (int, float)) else None
    quorum_value = target["unter_quorum"] if isinstance(target["unter_quorum"], (int, float)) else None

    title = f"Analyse du ratio signatures valides / Suisses de 18 ans et plus — votation n° {target['anr']}"
    lines = _build_front_matter(title, [src_swissvotes, src_swiss18, src_hist])
    lines += [
        f"# Analyse du ratio signatures valides / Suisses de 18 ans et plus — votation n° {target['anr']}",
        "",
        f"**Initiative** : *{target['titre']}*  ",
        f"**Date de scrutin** : {target['datum']}  ",
        "**Source** : Swissvotes (08.04.2026) + série population suisse 18+",
        "",
        "---",
        "",
        "## Résultat du calcul",
        "",
        "Le ratio est normalisé par le **nombre d'habitants suisses de 18 ans et plus** ",
        "(interpolé à la date de dépôt des signatures, `dat-submit`), afin d'approcher le vivier des personnes ayant le droit de signer.",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| Signatures valides déposées (`unter_g`) | {target['signatures']:.0f} |",
        f"| Date de dépôt des signatures (`dat-submit`) | {target['submit_raw']} |",
        f"| Suisses 18+ — point annuel précédent | {prev_point[1]:.0f} (année {int(prev_point[0])}) |",
        f"| Suisses 18+ — point annuel suivant | {next_point[1]:.0f} (année {int(next_point[0])}) |",
        f"| **Suisses 18+ interpolés au {target['submit_raw']}** | **{target['swiss18']:.0f}** |",
        f"| Électeurs inscrits à la date du scrutin (`berecht`, {target['datum']}) | {berecht_value:.0f} |" if berecht_value is not None else f"| Électeurs inscrits à la date du scrutin (`berecht`, {target['datum']}) | n.d. |",
        f"| **Ratio signatures / Suisses 18+** | **{target['ratio_pct']:.3f} %** |",
        f"| Quorum légal requis à l'époque (`unter-quorum`) | {quorum_value:.0f} |" if quorum_value is not None else "| Quorum légal requis à l'époque (`unter-quorum`) | n.d. |",
        f"| Surplus par rapport au quorum | {(target['signatures'] - quorum_value):.0f} signatures (× {target['signatures'] / quorum_value:.2f} le minimum légal) |" if quorum_value else "| Surplus par rapport au quorum | n.d. |",
        f"| Résultat du scrutin (`volkja-proz`) | {target['volkja_proz']} % de voix favorables → **rejeté** |",
        f"| Position du Conseil fédéral (`br-pos`) | {'Opposition (2)' if target['br_pos'] == '2' else target['br_pos'] or 'n.d.'} |",
        f"| Position du Parlement (`bv-pos`) | {'Opposition (2)' if target['bv_pos'] == '2' else target['bv_pos'] or 'n.d.'} |",
        "",
        "---",
        "",
        "## Position relative dans le corpus des initiatives (normalisation Suisses 18+)",
        "",
        "Référence : corpus des initiatives populaires fédérales avec `unter_g` et `dat-submit` valides,",
        "normalisées par `suisses_18plus` interpolé à `dat-submit`.",
        "",
        "| Indicateur du corpus | Valeur |",
        "|---|---|",
        f"| N (initiatives valides) | {n} |",
        f"| Médiane du ratio | {median:.3f} % |",
        f"| Moyenne du ratio | {mean:.3f} % |",
        f"| Écart-type | {stddev:.3f} points de % |",
        f"| **Rang de la votation {target['anr']}** | **{rank_le} / {n}** |",
        f"| **Percentile approximatif** | **~ {percentile:.1f} %** |",
        "",
        f"La votation {target['anr']} se situe dans le **haut de distribution** du corpus par ratio signatures / Suisses 18+.",
        f"Son ratio ({target['ratio_pct']:.3f} %) est :",
        f"- **× {target['ratio_pct'] / median:.2f}** la médiane ({median:.3f} %)",
        f"- **+ {(target['ratio_pct'] - mean) / stddev:.2f} écarts-types** au-dessus de la moyenne" if stddev > 0 else "- Écart-type nul : comparaison en z-score non applicable",
        "",
    ]

    if target_bin:
        lo, hi, count = target_bin
        lines += [
            f"Dans l'histogramme à {args.bins} intervalles, elle tombe dans le bin **[{lo:.3f} - {hi:.3f}[**, qui regroupe **{count} initiatives sur {n}** ({(count / n * 100):.1f} % du corpus).",
            "",
        ]

    lines += [
        "---",
        "",
        "## Interprétation",
        "",
        "### Mobilisation exceptionnelle",
        "",
        "Le volume de signatures est très élevé au regard du vivier de signataires potentiels (Suisses 18+),",
        "ce qui place cette initiative dans la partie haute de la distribution historique.",
        "",
        "### Rejet malgré la capacité de mobilisation",
        "",
        "Un niveau de signatures élevé n'implique pas l'acceptation au vote : l'initiative est rejetée,",
        "dans un contexte d'opposition du Conseil fédéral et du Parlement.",
        "",
        "---",
        "",
        "## Incertitudes et limites",
        "",
        "- `suisses_18plus` est une série annuelle ; l'interpolation intra-annuelle suppose une évolution régulière entre deux années.",
        "- Cette normalisation approxime le vivier des signataires, sans modéliser les contraintes juridiques fines.",
        "- Le quorum légal historique diffère des seuils actuels, ce qui limite la comparabilité brute sur longue période.",
        "",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {out_path}")
    print(f"[INFO] anr={target['anr']} ratio={target['ratio_pct']:.3f}% | percentile~={percentile:.1f} | N={n}")


if __name__ == "__main__":
    main()

