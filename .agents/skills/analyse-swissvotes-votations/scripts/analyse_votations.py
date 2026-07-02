#!/usr/bin/env python3
"""
analyse_votations.py — Skill analyse-swissvotes-votations
Extrait et compare les métadonnées de votations fédérales suisses
à partir du jeu de données Swissvotes.

Usage:
  python -u analyse_votations.py --votation-ids 86
  python -u analyse_votations.py --votation-ids 86,119 --json
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Chemins par défaut (relatifs à la racine du projet)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", "..", ".."))
_DEFAULT_CSV = os.path.join(
    _PROJECT_ROOT,
    ".agents", "skills", "analyse-swissvotes-votations", "assets",
    "DATASET CSV 08-04-2026.csv",
)
_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "sources/swissvotes")

# ---------------------------------------------------------------------------
# Codes de valeur lisibles
# ---------------------------------------------------------------------------
RECHTSFORM = {
    "1": "Référendum obligatoire",
    "2": "Référendum facultatif",
    "3": "Initiative populaire",
    "4": "Contre-projet direct",
    "5": "Question subsidiaire",
}
POSITION = {
    "1": "Favorable (oui)",
    "2": "Opposé (non)",
    "3": "Sans recommandation",
    "8": "Préfère le contre-projet",
    "9": "Préfère l'initiative",
    ".": "Inconnu",
    "": "–",
}

# Colonnes clés à extraire
KEY_DATE_COLS = [
    ("dat-preexam", "Pré-examen"),
    ("dat-start",   "Début récolte"),
    ("dat-limit",   "Fin légale récolte"),
    ("dat-submit",  "Dépôt signatures"),
    ("dat-success", "Constatation succès"),
    ("dat-message", "Message CF au Parlement"),
    ("dat-parl",    "Décision du Parlement"),
    ("datum",       "Jour du scrutin"),
    ("dat-force",   "Entrée en vigueur"),
]
KEY_DURATION_COLS = [
    ("sammelfrist",   "Durée légale récolte (j)"),
    ("dauer_bv",      "Traitement parlementaire (j)"),
    ("dauer_abst",    "Parlement → scrutin (j)"),
    ("i-dauer_samm",  "Récolte effective — initiatives (j)"),
    ("i-dauer_br",    "Dépôt → message CF — initiatives (j)"),
    ("i-dauer_tot",   "Durée totale — initiatives (j)"),
    ("fr-dauer_samm", "Récolte effective — réf. facultatif (j)"),
    ("fr-dauer_tot",  "Durée totale — réf. facultatif (j)"),
    ("sparedays",     "Jours restants à la récolte lors du dépôt"),
]
KEY_SIG_COLS = [
    ("unter-quorum", "Quorum requis"),
    ("unter_g",      "Signatures valides"),
    ("unter_u",      "Signatures invalides"),
]
KEY_RESULT_COLS = [
    ("volkja-proz", "% voix favorables"),
]
KEY_POSITION_COLS = [
    ("br-pos", "Position du Conseil fédéral"),
    ("bv-pos", "Position du Parlement"),
    ("nr-pos", "Position du Conseil national"),
    ("sr-pos", "Position du Conseil des États"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader)


def _parse_date(raw: str) -> date | None:
    """Convertit une valeur de date CSV (YYYY-MM-DD ou DD.MM.YYYY) en objet date."""
    if not raw or raw.strip() in ("", ".", "0", "9999"):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _fmt_date(raw: str) -> str:
    d = _parse_date(raw)
    if d:
        return d.strftime("%d.%m.%Y")
    if raw.strip() == "0":
        return "– (sans objet)"
    if raw.strip() == "9999":
        return "– (illimitée)"
    if raw.strip() in (".", ""):
        return "– (données manquantes)"
    return raw.strip()


def _fmt_days(raw: str) -> str:
    if not raw or raw.strip() in ("", "."):
        return "– (données manquantes)"
    if raw.strip() == "0":
        return "– (sans objet)"
    if raw.strip() == "9999":
        return "– (illimitée)"
    try:
        days = float(raw.strip().replace(",", "."))
        if days > 90:
            months = days / 30.44
            return f"{int(days)} j (~{months:.1f} mois)"
        return f"{int(days)} j"
    except ValueError:
        return raw.strip()


def _position_label(raw: str) -> str:
    return POSITION.get(raw.strip(), raw.strip())


def _is_field_expected_for_type(col: str, rechtsform_code: str) -> bool:
    """Indique si une colonne fait sens pour le type de votation donné."""
    code = (rechtsform_code or "").strip()
    if code.endswith(".0"):
        code = code[:-2]
    if col.startswith("i-"):
        return code == "3"  # Initiative populaire
    if col.startswith("fr-"):
        return code == "2"  # Référendum facultatif
    return True


def _days_between(raw_a: str, raw_b: str) -> str | None:
    a = _parse_date(raw_a)
    b = _parse_date(raw_b)
    if a and b:
        delta = (b - a).days
        return f"{delta} j" + (f" (~{delta/30.44:.1f} mois)" if delta > 90 else "")
    return None


def _missing_fields(row: dict, cols: list[tuple]) -> list[str]:
    missing = []
    for col, label in cols:
        val = row.get(col, "").strip()
        if val in (".", ""):
            missing.append(f"`{col}` ({label}) : données manquantes")
        elif val == "0" and col.startswith("dat-"):
            missing.append(f"`{col}` ({label}) : sans objet (pas de récolte)")
        elif val == "9999":
            missing.append(f"`{col}` ({label}) : valeur illimitée (avant 1978)")
    return missing


# ---------------------------------------------------------------------------
# Construction des métadonnées d'une votation
# ---------------------------------------------------------------------------

def _extract_metadata(row: dict) -> dict:
    anr = row.get("anr", "").strip()
    rechtsform_code = row.get("rechtsform", "").strip()

    meta = {
        "anr": anr,
        "datum": row.get("datum", "").strip(),
        "titre_court": row.get("titel_kurz_f", "").strip() or row.get("titel_kurz_d", "").strip(),
        "titre_officiel": row.get("titel_off_f", "").strip() or row.get("titel_off_d", "").strip(),
        "type": RECHTSFORM.get(rechtsform_code, rechtsform_code),
        "rechtsform_code": rechtsform_code,
        "urheber": row.get("urheber-fr", "").strip() or row.get("urheber", "").strip(),
        "dates": {col: row.get(col, "").strip() for col, _ in KEY_DATE_COLS},
        "durees": {col: row.get(col, "").strip() for col, _ in KEY_DURATION_COLS},
        "signatures": {col: row.get(col, "").strip() for col, _ in KEY_SIG_COLS},
        "positions": {col: row.get(col, "").strip() for col, _ in KEY_POSITION_COLS},
        "volkja_proz": row.get("volkja-proz", "").strip(),
    }

    # Durée calculée : fin de récolte → scrutin (non précalculée dans Swissvotes)
    meta["duree_limit_to_datum"] = _days_between(
        meta["dates"].get("dat-limit", ""),
        meta["dates"].get("datum", ""),
    )

    return meta


# ---------------------------------------------------------------------------
# Rendu Markdown — fiche unique
# ---------------------------------------------------------------------------

def _render_fiche(meta: dict) -> str:
    lines = []

    lines.append("## Fiche de la votation\n")
    lines.append(f"| Champ | Valeur |")
    lines.append(f"| ----- | ------ |")
    lines.append(f"| Numéro | {meta['anr']} |")
    lines.append(f"| Date du scrutin | {_fmt_date(meta['datum'])} |")
    lines.append(f"| Titre court | {meta['titre_court']} |")
    lines.append(f"| Titre officiel | {meta['titre_officiel']} |")
    lines.append(f"| Type | {meta['type']} |")
    if meta["urheber"]:
        lines.append(f"| Comité / auteurs | {meta['urheber']} |")
    lines.append("")

    lines.append("## Chronologie\n")
    prev_date_raw = None
    prev_label = None
    for col, label in KEY_DATE_COLS:
        raw = meta["dates"].get(col, "")
        fmt = _fmt_date(raw)
        interval = ""
        if prev_date_raw and raw and raw.strip() not in ("", ".", "0", "9999"):
            d = _days_between(prev_date_raw, raw)
            if d:
                interval = f" _(+{d} depuis {prev_label})_"
        lines.append(f"- **{label}** : {fmt}{interval}")
        if raw.strip() not in ("", ".", "0", "9999"):
            prev_date_raw = raw
            prev_label = label
    lines.append("")

    if meta["duree_limit_to_datum"]:
        lines.append(
            f"> **Durée entre la fin légale de la récolte et le scrutin** : "
            f"{meta['duree_limit_to_datum']}\n"
        )

    lines.append("### Durées (précalculées Swissvotes)\n")
    lines.append("| Indicateur | Valeur |")
    lines.append("| ---------- | ------ |")
    for col, label in KEY_DURATION_COLS:
        val = meta["durees"].get(col, "")
        lines.append(f"| {label} | {_fmt_days(val)} |")
    lines.append("")

    lines.append("### Signatures\n")
    lines.append("| Indicateur | Valeur |")
    lines.append("| ---------- | ------ |")
    for col, label in KEY_SIG_COLS:
        val = meta["signatures"].get(col, "")
        lines.append(f"| {label} | {val if val and val not in ('.', '0') else '–'} |")
    lines.append("")

    lines.append("## Résultat\n")
    pct = meta["volkja_proz"]
    if pct and pct not in (".", ""):
        lines.append(f"- **Voix favorables** : {pct.replace('.', ',')} %")
    lines.append("")
    lines.append("### Positions des acteurs\n")
    lines.append("| Acteur | Position |")
    lines.append("| ------ | -------- |")
    for col, label in KEY_POSITION_COLS:
        val = meta["positions"].get(col, "")
        lines.append(f"| {label} | {_position_label(val)} |")
    lines.append("")

    all_cols = KEY_DATE_COLS + KEY_DURATION_COLS + KEY_SIG_COLS + KEY_RESULT_COLS + KEY_POSITION_COLS
    all_raw = {**meta["dates"], **meta["durees"], **meta["signatures"],
               "volkja-proz": meta["volkja_proz"], **meta["positions"]}
    missing = []
    for col, label in all_cols:
        if not _is_field_expected_for_type(col, meta["rechtsform_code"]):
            continue
        val = all_raw.get(col, "").strip()
        if val in (".", ""):
            missing.append(f"- `{col}` ({label}) : données manquantes")
        elif val == "0" and col.startswith("dat-"):
            missing.append(f"- `{col}` ({label}) : sans objet (pas de récolte)")
        elif val == "9999":
            missing.append(f"- `{col}` ({label}) : valeur illimitée / inapplicable (avant 1978)")

    if int(meta["anr"]) in (665, 666, 671):
        missing.append(
            "- **Gel Covid** : `i-dauer_tot` exclut 72 jours de suspension de la récolte "
            "(ordonnance du CF du 20.03.2020, AS 2020 847)"
        )

    lines.append("## Incertitudes et données manquantes\n")
    if missing:
        lines.extend(missing)
    else:
        lines.append("_Aucune donnée manquante détectée pour les champs clés._")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rendu Markdown — comparaison
# ---------------------------------------------------------------------------

def _render_comparison(metas: list[dict]) -> str:
    lines = []

    # Tableau comparatif
    lines.append("## Tableau comparatif\n")

    # En-tête
    header_cols = [
        ("anr", "N°"),
        ("datum", "Scrutin"),
        ("titre_court", "Titre"),
        ("type", "Type"),
        ("volkja_proz", "% Oui"),
    ]
    # Durées pertinentes
    dur_cols = [
        ("sammelfrist",        "Récolte légale (j)"),
        ("dauer_bv",           "Traitement parl. (j)"),
        ("dauer_abst",         "Parl.→scrutin (j)"),
        ("i-dauer_samm",       "Récolte eff. init. (j)"),
        ("i-dauer_tot",        "Total init. (j)"),
        ("fr-dauer_samm",      "Récolte eff. réf. (j)"),
        ("fr-dauer_tot",       "Total réf. fac. (j)"),
    ]

    all_header = [label for _, label in header_cols] + [label for _, label in dur_cols] + ["Fin récolte→scrutin"]
    sep = ["---"] * len(all_header)
    lines.append("| " + " | ".join(all_header) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    for m in metas:
        row_vals = []
        for col, _ in header_cols:
            if col == "datum":
                row_vals.append(_fmt_date(m.get(col, "")))
            elif col == "volkja_proz":
                pct = m.get(col, "")
                row_vals.append(f"{pct.replace('.', ',')} %" if pct and pct not in (".", "") else "–")
            else:
                row_vals.append(m.get(col, ""))
        for col, _ in dur_cols:
            row_vals.append(_fmt_days(m["durees"].get(col, "")))
        row_vals.append(m.get("duree_limit_to_datum") or "–")
        lines.append("| " + " | ".join(str(v) for v in row_vals) + " |")

    lines.append("")
    lines.append("Le 'traitement parlementaire' est la durée entre le message du conseil fédéral et la fin des débats du parlement.")

    # Analyse des écarts
    lines.append("## Analyse des écarts\n")

    numeric_dur = [
        ("sammelfrist",   "durée légale de récolte"),
        ("dauer_bv",      "traitement parlementaire"),
        ("dauer_abst",    "délai parlement → scrutin"),
        ("i-dauer_tot",   "durée totale initiative"),
        ("fr-dauer_tot",  "durée totale référendum facultatif"),
    ]
    for col, label_fr in numeric_dur:
        vals = []
        for m in metas:
            raw = m["durees"].get(col, "").strip()
            try:
                v = float(raw.replace(",", "."))
                vals.append((m["anr"], m["titre_court"], v))
            except (ValueError, AttributeError):
                pass
        if len(vals) >= 2:
            vals.sort(key=lambda x: x[2])
            mini = vals[0]
            maxi = vals[-1]
            diff = maxi[2] - mini[2]
            lines.append(
                f"- **{label_fr.capitalize()}** : "
                f"votation n°\u202f{mini[0]} ({mini[1]}) = {int(mini[2])}\u202fj, "
                f"votation n°\u202f{maxi[0]} ({maxi[1]}) = {int(maxi[2])}\u202fj "
                f"→ écart de {int(diff)}\u202fj"
                + (f" (~{diff/30.44:.1f}\u202fmois)" if diff > 90 else "")
            )

    # % oui
    pcts = []
    for m in metas:
        raw = m.get("volkja_proz", "").strip()
        try:
            pcts.append((m["anr"], m["titre_court"], float(raw.replace(",", "."))))
        except (ValueError, AttributeError):
            pass
    if len(pcts) >= 2:
        pcts.sort(key=lambda x: x[2])
        lines.append(
            f"- **% de voix favorables** : "
            f"votation n°\u202f{pcts[0][0]} ({pcts[0][1]}) = {pcts[0][2]:.1f}\u202f%, "
            f"votation n°\u202f{pcts[-1][0]} ({pcts[-1][1]}) = {pcts[-1][2]:.1f}\u202f%"
        )

    lines.append("")

    # Incertitudes
    lines.append("## Incertitudes et données manquantes\n")
    all_missing = False
    for m in metas:
        all_cols = KEY_DATE_COLS + KEY_DURATION_COLS + KEY_SIG_COLS
        all_raw = {**m["dates"], **m["durees"], **m["signatures"]}
        for col, label in all_cols:
            if not _is_field_expected_for_type(col, m["rechtsform_code"]):
                continue
            val = all_raw.get(col, "").strip()
            if val in (".", ""):
                lines.append(f"- Votation n°\u202f{m['anr']} — `{col}` ({label}) : données manquantes")
                all_missing = True
            elif val == "9999":
                lines.append(
                    f"- Votation n°\u202f{m['anr']} — `{col}` ({label}) : valeur illimitée / inapplicable (avant 1978)"
                )
                all_missing = True
        if int(m["anr"]) in (665, 666, 671):
            lines.append(
                f"- Votation n°\u202f{m['anr']} — **Gel Covid** : `i-dauer_tot` exclut 72 jours "
                "de suspension (AS 2020 847)"
            )
            all_missing = True
    if not all_missing:
        lines.append("_Aucune donnée manquante détectée pour les champs clés._")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse et comparaison de métadonnées de votations Swissvotes."
    )
    parser.add_argument(
        "--votation-ids", required=True,
        help="Numéros de votations séparés par des virgules (ex. 86,119)"
    )
    parser.add_argument(
        "--csv", default=_DEFAULT_CSV,
        help="Chemin vers le CSV Swissvotes"
    )
    parser.add_argument(
        "--output", default=None,
        help="Chemin du fichier de sortie Markdown"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Produit aussi un fichier JSON"
    )
    args = parser.parse_args()

    ids = [x.strip() for x in args.votation_ids.split(",") if x.strip()]
    ids_slug = "_".join(ids)

    # Lecture CSV
    if not os.path.isfile(args.csv):
        print(f"[ERREUR] Fichier CSV introuvable : {args.csv}", file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Lecture du CSV : {args.csv}")
    rows = _read_csv(args.csv)
    rows_by_id = {r["anr"].strip(): r for r in rows}

    # Récupération des votations demandées
    metas = []
    not_found = []
    for vid in ids:
        if vid in rows_by_id:
            metas.append(_extract_metadata(rows_by_id[vid]))
        else:
            not_found.append(vid)

    if not_found:
        print(f"[AVERTISSEMENT] Votations introuvables dans le CSV : {', '.join(not_found)}", file=sys.stderr)
    if not metas:
        print("[ERREUR] Aucune votation trouvée.", file=sys.stderr)
        sys.exit(1)

    # Chemin de sortie
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    if (len(ids)==1):
        out_md = args.output or os.path.join(_OUTPUT_DIR, f"votation_{ids_slug}/analyse_duree_votation.md")
    else:
        # compare multiple votations
        out_md = args.output or os.path.join(_OUTPUT_DIR, f"analyse_comparaison_votations_{ids_slug}.md")

    # Front matter YAML
    today = datetime.now().strftime("%Y-%m-%d")
    titre_type = "Fiche" if len(metas) == 1 else "Comparaison"
    titre = f"{titre_type} de la votation n°\u202f{ids_slug}" if len(metas) == 1 else \
            f"Comparaison des votations n°\u202f{', '.join(ids)}"
    front_matter = (
        "---\n"
        f'title: "{titre}"\n'
        f'date_publication: "{today}"\n'
        'author: "skill analyse-swissvotes-votations"\n'
        f'votation_ids: [{", ".join(ids)}]\n'
        "---\n\n"
    )

    # Corps
    if len(metas) == 1:
        m = metas[0]
        body = f"# Fiche — Votation n°\u202f{m['anr']} — {m['titre_court']}\n\n"
        body += _render_fiche(m)
    else:
        body = f"# Comparaison des votations n°\u202f{', '.join(ids)}\n\n"
        body += _render_comparison(metas)

    md_content = front_matter + body

    # Écriture Markdown
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[OK] Fichier Markdown écrit : {out_md}")

    # Écriture JSON (optionnel)
    if args.json:
        out_json = os.path.splitext(out_md)[0] + ".json"
        payload = {
            "generated": today,
            "author": "skill analyse-swissvotes-votations",
            "votation_ids": ids,
            "votations": metas,
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        print(f"[OK] Fichier JSON écrit : {out_json}")


if __name__ == "__main__":
    main()

