#!/usr/bin/env python3
"""Exporte une estimation du nombre d'habitants suisses de 18 ans et plus par annee.

Sources utilisees (et uniquement celles-ci):
- JSON de pyramide des ages: data[year][sex][age][A|B|C]["eff"]
- CSV du pourcentage d'etrangers en Suisse par annee

Methode:
1) Calcul du total 18+ (H+F) depuis le JSON (scenario A/B/C, par defaut A)
2) Estimation du pourcentage d'etrangers par annee via interpolation lineaire
   dans le CSV fourni (bornes clampes hors intervalle)
3) Habitants suisses 18+ = total_18plus * (1 - pct_etrangers/100)
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_JSON = SKILL_DIR / "assets" / "ds-x-01.03.01.02.master.json"
DEFAULT_ETRANGERS_CSV = SKILL_DIR / "assets" / "pourcentage_etrangers_en_suisse.csv"
DEFAULT_OUTPUT = SKILL_DIR / "assets" / "habitants_suisses_18plus_par_annee.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estime le nombre d'habitants suisses de 18 ans et plus par annee."
    )
    parser.add_argument("--input-json", type=Path, default=DEFAULT_JSON, help="Chemin du JSON source")
    parser.add_argument(
        "--input-etrangers-csv",
        type=Path,
        default=DEFAULT_ETRANGERS_CSV,
        help="Chemin du CSV des pourcentages d'etrangers",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Chemin du CSV de sortie")
    parser.add_argument(
        "--scenario",
        choices=["A", "B", "C"],
        default="A",
        help="Scenario demographique JSON a utiliser (A/B/C).",
    )
    return parser.parse_args()


def as_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return 0
        raw = raw.replace("'", "").replace(" ", "")
        return int(float(raw))
    return 0


def as_float(value: str) -> float:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("valeur vide")
    raw = raw.replace("%", "").replace(" ", "").replace(",", ".")
    return float(raw)


def load_foreigner_percentages(path: Path) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            year_raw = (row.get("annee") or "").strip()
            pct_raw = (row.get("pourcentage_etrangers[%]") or "").strip()
            if not year_raw or not pct_raw:
                continue
            points.append((int(year_raw), as_float(pct_raw)))
    points.sort(key=lambda item: item[0])
    if not points:
        raise ValueError("Aucun point de pourcentage d'etrangers n'a ete charge.")
    return points


def interpolate_pct(year: int, points: list[tuple[int, float]]) -> float:
    if year <= points[0][0]:
        return points[0][1]
    if year >= points[-1][0]:
        return points[-1][1]

    for i in range(len(points) - 1):
        y0, p0 = points[i]
        y1, p1 = points[i + 1]
        if y0 <= year <= y1:
            if y1 == y0:
                return p0
            ratio = (year - y0) / (y1 - y0)
            return p0 + ratio * (p1 - p0)

    return points[-1][1]


def compute_total_18plus(year_data: dict, scenario: str) -> int:
    total = 0
    for sex in ("M", "F"):
        sex_map = year_data.get(sex)
        if not isinstance(sex_map, dict):
            continue
        for age_str, scenario_map in sex_map.items():
            try:
                age = int(age_str)
            except (TypeError, ValueError):
                continue
            if age < 18:
                continue

            if not isinstance(scenario_map, dict):
                continue
            cell = scenario_map.get(scenario)
            if not isinstance(cell, dict):
                continue
            total += as_int(cell.get("eff"))
    return total


def export_csv(input_json: Path, input_etrangers_csv: Path, output_csv: Path, scenario: str) -> int:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Le JSON ne contient pas de champ 'data' valide.")

    pct_points = load_foreigner_percentages(input_etrangers_csv)

    rows: list[tuple[int, int, float, float, int]] = []
    for year_str, year_data in data.items():
        if not isinstance(year_data, dict):
            continue
        try:
            year = int(year_str)
        except (TypeError, ValueError):
            continue

        total_18plus = compute_total_18plus(year_data, scenario)
        pct_etrangers = interpolate_pct(year, pct_points)
        pct_suisses = max(0.0, min(100.0, 100.0 - pct_etrangers))
        suisses_18plus = int(round(total_18plus * (pct_suisses / 100.0)))

        rows.append((year, total_18plus, pct_etrangers, pct_suisses, suisses_18plus))

    rows.sort(key=lambda item: item[0])
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "annee",
                "habitants_total_18plus",
                "pourcentage_etrangers_estime[%]",
                "pourcentage_suisses_estime[%]",
                "habitants_suisses_18plus_estimes",
            ]
        )
        for year, total_18plus, pct_etrangers, pct_suisses, suisses_18plus in rows:
            writer.writerow(
                [
                    year,
                    total_18plus,
                    f"{pct_etrangers:.4f}",
                    f"{pct_suisses:.4f}",
                    suisses_18plus,
                ]
            )

    return len(rows)


def main() -> int:
    args = parse_args()

    if not args.input_json.exists():
        raise SystemExit(f"[ERREUR] JSON introuvable: {args.input_json}")
    if not args.input_etrangers_csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.input_etrangers_csv}")

    row_count = export_csv(
        input_json=args.input_json,
        input_etrangers_csv=args.input_etrangers_csv,
        output_csv=args.output,
        scenario=args.scenario,
    )
    print(f"[OK] CSV ecrit: {args.output}")
    print(f"[INFO] Annees exportees: {row_count} | scenario: {args.scenario}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

