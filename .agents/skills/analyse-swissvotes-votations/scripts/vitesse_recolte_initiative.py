#!/usr/bin/env python3
"""
Calcule la vitesse de récolte des signatures pour une initiative donnée.

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/vitesse_recolte_initiative.py" --votation-id 86
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"


def _parse_date(value: str):
    raw = (value or "").strip()
    if raw in ("", ".", "0", "9999"):
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def _parse_number(value: str):
    raw = (value or "").strip()
    if raw in ("", ".", "0", "9999"):
        return None
    raw = raw.replace("'", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _build_front_matter(title: str, source_rel: str) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        "---",
        f'title: "{title.replace("\"", "'")}"',
        f'date_publication: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
        f'  - "{source_rel}"',
        "---",
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcule la vitesse de récolte des signatures pour une initiative Swissvotes."
    )
    parser.add_argument("--votation-id", required=True, help="Numéro de votation (anr), ex: 86")
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV, help="Chemin du CSV Swissvotes")
    parser.add_argument("--output", type=Path, default=None, help="Fichier Markdown de sortie")
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.csv}")

    votation_id = str(args.votation_id).strip()
    out_path = args.output or (_PROJECT_ROOT / "sources" / "swissvotes" / f"votation_{votation_id}" / "vitesse_recolte_initiative.md")

    rows = []
    target = None

    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            start = _parse_date(row.get("dat-start", ""))
            submit = _parse_date(row.get("dat-submit", ""))
            signatures = _parse_number(row.get("unter_g", ""))
            if not start or not submit or signatures is None:
                continue

            days = (submit - start).days
            if days <= 0 or signatures <= 0:
                continue

            speed = signatures / days
            anr = (row.get("anr", "") or "").strip()
            titre = (row.get("titel_kurz_f", "") or row.get("titel_kurz_d", "") or "").strip()
            rec = {
                "anr": anr,
                "titre": titre,
                "start_raw": (row.get("dat-start", "") or "").strip(),
                "submit_raw": (row.get("dat-submit", "") or "").strip(),
                "days": days,
                "signatures": signatures,
                "speed": speed,
            }
            rows.append(rec)
            if anr == votation_id:
                target = rec

    if not target:
        raise SystemExit(f"[ERREUR] Votation {votation_id} introuvable ou données incomplètes pour le calcul.")

    speeds = sorted(r["speed"] for r in rows)
    n = len(speeds)
    median = speeds[n // 2] if n % 2 == 1 else (speeds[n // 2 - 1] + speeds[n // 2]) / 2
    rank_le = sum(1 for v in speeds if v <= target["speed"])
    percentile = rank_le / n * 100

    try:
        source_rel = args.csv.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        source_rel = args.csv.resolve().as_posix()

    title = f"Vitesse de récolte — initiative {target['anr']}"
    lines = _build_front_matter(title, source_rel)
    lines += [
        f"# Vitesse de récolte des signatures — initiative {target['anr']}",
        "",
        f"## {target['titre']}",
        "",
        "## Résultat",
        "",
        "| Indicateur | Valeur |",
        "|---|---|",
        f"| Début de récolte (`dat-start`) | {target['start_raw']} |",
        f"| Dépôt (`dat-submit`) | {target['submit_raw']} |",
        f"| Durée de récolte | {target['days']} jours |",
        f"| Signatures valides (`unter_g`) | {target['signatures']:.0f} |",
        f"| Vitesse moyenne | {target['speed']:.1f} signatures/jour |",
        "",
        "## Position relative parmi les initiatives",
        "",
        f"- Nombre d'initiatives comparables : **{n}**",
        f"- Médiane de vitesse : **{median:.1f} signatures/jour**",
        f"- Percentile approximatif de l'initiative : **{percentile:.1f}**",
        "",
        "## Notes méthodologiques",
        "",
        "- Formule : `vitesse = unter_g / (dat-submit - dat-start)`.",
        "- Le calcul est limité aux initiatives (`rechtsform = 3`) avec dates et signatures valides.",
        "",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {out_path}")
    print(f"[INFO] anr={target['anr']} speed={target['speed']:.1f} sig/j | percentile~={percentile:.1f}")


if __name__ == "__main__":
    main()

