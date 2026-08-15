#!/usr/bin/env python3
"""
Interroger le cadastre energetique vaudois (table `regener`) avec du langage naturel.

Le script detecte des intentions frequentes (statistiques globales, top communes,
mazout, repartitions) et execute des requetes SQL parametrees.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_ROOT / "assets"
DEFAULT_DB_PATH = ASSETS_DIR / "Cadastre_energetique_des_batiments_vaudois_103-VD.1.gpkg"
DEFAULT_SCHEMA_MD = ASSETS_DIR / "MGDM_103VD_EnergetiqueBatiments_V1.1.2.md"


@dataclass
class QueryPlan:
    title: str
    sql: str
    params: tuple[Any, ...] = ()


def _normalize(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "e": "e",
        "é": "e",
        "è": "e",
        "ê": "e",
        "à": "a",
        "â": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
        "œ": "oe",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _extract_top_n(q: str, default: int) -> int:
    m = re.search(r"\btop\s*(\d{1,3})\b", q)
    if m:
        return max(1, min(int(m.group(1)), 200))
    m = re.search(r"\b(\d{1,3})\s*(communes?|resultats?|lignes?|batiments?)\b", q)
    if m:
        return max(1, min(int(m.group(1)), 200))
    return default


def _plan_intent(question: str) -> QueryPlan:
    q = _normalize(question)

    if q.startswith("sql:"):
        sql = question.split(":", 1)[1].strip()
        _validate_safe_sql(sql)
        return QueryPlan(title="Requete SQL explicite", sql=sql)

    if any(k in q for k in ["stats", "statistiques", "vue d'ensemble", "global"]):
        return QueryPlan(
            title="Statistiques generales",
            sql=(
                "SELECT "
                "COUNT(*) AS nb_batiments, "
                "COUNT(DISTINCT ggdenr) AS nb_communes, "
                "COALESCE(SUM(co2_dir_tot), 0) AS co2_total_kg, "
                "COALESCE(SUM(besoins_ch), 0) AS besoins_ch_total "
                "FROM regener"
            ),
        )

    if "top" in q and "commune" in q and ("co2" in q or "emission" in q):
        top_n = _extract_top_n(q, 10)
        return QueryPlan(
            title=f"Top {top_n} communes par CO2 direct",
            sql=(
                "SELECT ggdenr, ggdename AS commune, COUNT(*) AS nb_batiments, "
                "COALESCE(SUM(co2_dir_tot), 0) AS co2_kg, "
                "COALESCE(AVG(co2_dir_tot), 0) AS co2_moy_kg "
                "FROM regener "
                "GROUP BY ggdenr, ggdename "
                "ORDER BY co2_kg DESC "
                "LIMIT ?"
            ),
            params=(top_n,),
        )

    if ("energie" in q or "chauffage" in q or "genh1" in q) and ("repartition" in q or "distribution" in q):
        top_n = _extract_top_n(q, 15)
        return QueryPlan(
            title=f"Repartition energie de chauffage (top {top_n})",
            sql=(
                "SELECT COALESCE(genh1, 'Non renseigne') AS energie, "
                "COUNT(*) AS nb_batiments, "
                "ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM regener), 1) AS pct, "
                "COALESCE(SUM(co2_dir_tot), 0) AS co2_kg "
                "FROM regener "
                "GROUP BY genh1 "
                "ORDER BY nb_batiments DESC "
                "LIMIT ?"
            ),
            params=(top_n,),
        )

    if "mazout" in q and ("analyse" in q or "resume" in q or "stat" in q):
        return QueryPlan(
            title="Analyse des batiments chauffes au mazout",
            sql=(
                "SELECT "
                "COUNT(*) AS nb_batiments, "
                "COALESCE(SUM(co2_dir_tot), 0) AS co2_total_kg, "
                "COALESCE(AVG(co2_dir_tot), 0) AS co2_moy_kg, "
                "COALESCE(AVG(gebf), 0) AS gebf_moy, "
                "COALESCE(AVG(besoins_ch), 0) AS besoins_ch_moy "
                "FROM regener WHERE genh1 = 'Mazout'"
            ),
        )

    if "mazout" in q and "commune" in q:
        top_n = _extract_top_n(q, 20)
        return QueryPlan(
            title=f"Top {top_n} communes par nombre de batiments au mazout",
            sql=(
                "SELECT ggdenr, ggdename AS commune, COUNT(*) AS nb_mazout, "
                "COALESCE(SUM(co2_dir_tot), 0) AS co2_kg "
                "FROM regener "
                "WHERE genh1 = 'Mazout' "
                "GROUP BY ggdenr, ggdename "
                "ORDER BY nb_mazout DESC "
                "LIMIT ?"
            ),
            params=(top_n,),
        )

    if "epoque" in q and ("repartition" in q or "distribution" in q):
        return QueryPlan(
            title="Repartition par epoque energetique",
            sql=(
                "SELECT COALESCE(ener_epoque, 'Non renseignee') AS epoque, "
                "COUNT(*) AS nb_batiments, "
                "ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM regener), 1) AS pct, "
                "COALESCE(AVG(co2_dir_tot), 0) AS co2_moy_kg "
                "FROM regener "
                "GROUP BY ener_epoque "
                "ORDER BY nb_batiments DESC"
            ),
        )

    commune_id = _extract_commune_id(q)
    if commune_id is not None and ("batiment" in q or "liste" in q):
        limit_n = _extract_top_n(q, 200)
        return QueryPlan(
            title=f"Liste des batiments pour la commune OFS {commune_id}",
            sql=(
                "SELECT egid, ggdenr, ggdename, id_empreinte, genh1, genw1, gbauj, "
                "ener_epoque, besoins_ch, besoins_ecs, co2_dir_tot, co2_indir_tot "
                "FROM regener "
                "WHERE ggdenr = ? "
                "ORDER BY egid "
                "LIMIT ?"
            ),
            params=(commune_id, limit_n),
        )

    plan = _plan_generic_metric(question, q)
    if plan is not None:
        return plan

    raise ValueError(
        "Question non reconnue. Exemples: 'top 10 communes par co2', "
        "'repartition energie chauffage', 'analyse mazout', "
        "'liste batiments commune 5434', ou 'sql: SELECT ...'."
    )


def _extract_commune_id(q: str) -> int | None:
    m = re.search(r"\bcommune\s+(\d{3,4})\b", q)
    if m:
        return int(m.group(1))
    return None


def _plan_generic_metric(question: str, q: str) -> QueryPlan | None:
    metric_sql = None
    metric_title = None

    if "combien" in q or "nombre" in q:
        metric_sql = "COUNT(*)"
        metric_title = "Nombre de batiments"
    elif "co2" in q and ("total" in q or "somme" in q):
        metric_sql = "COALESCE(SUM(co2_dir_tot), 0)"
        metric_title = "CO2 direct total (kg/an)"
    elif "co2" in q and ("moyen" in q or "moyenne" in q):
        metric_sql = "COALESCE(AVG(co2_dir_tot), 0)"
        metric_title = "CO2 direct moyen (kg/batiment)"
    elif "besoin" in q and ("chauffage" in q or "ch" in q):
        metric_sql = "COALESCE(SUM(besoins_ch), 0)"
        metric_title = "Besoins chauffage totaux (kWh/an)"

    if metric_sql is None:
        return None

    filters = []
    params: list[Any] = []

    if "mazout" in q:
        filters.append("genh1 = ?")
        params.append("Mazout")
    elif "gaz" in q:
        filters.append("genh1 = ?")
        params.append("Gaz")

    m = re.search(r"\bcommune\s+(\d{3,4})\b", q)
    if m:
        filters.append("ggdenr = ?")
        params.append(int(m.group(1)))

    where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"SELECT {metric_sql} AS valeur FROM regener{where_clause}"
    return QueryPlan(title=f"Mesure: {metric_title}", sql=sql, params=tuple(params))


def _validate_safe_sql(sql: str) -> None:
    low = sql.strip().lower()
    if not low.startswith("select"):
        raise ValueError("Seules les requetes SELECT sont autorisees avec 'sql:'.")
    forbidden = [";", "--", "/*", "*/", "insert", "update", "delete", "drop", "alter", "attach", "detach", "pragma"]
    if any(token in low for token in forbidden):
        raise ValueError("Requete SQL refusee pour raisons de securite.")


def _execute(conn: sqlite3.Connection, plan: QueryPlan) -> tuple[list[str], list[sqlite3.Row]]:
    cur = conn.cursor()
    cur.execute(plan.sql, plan.params)
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description] if cur.description else []
    return columns, rows


def _format_table(columns: list[str], rows: list[sqlite3.Row]) -> str:
    if not columns:
        return "(Aucune colonne retournee)"
    if not rows:
        return "(Aucun resultat)"

    widths = [len(col) for col in columns]
    matrix: list[list[str]] = []
    for row in rows:
        line = []
        for i, col in enumerate(columns):
            val = row[col]
            txt = "" if val is None else str(val)
            line.append(txt)
            widths[i] = max(widths[i], len(txt))
        matrix.append(line)

    sep = " | "
    header = sep.join(col.ljust(widths[i]) for i, col in enumerate(columns))
    rule = "-+-".join("-" * widths[i] for i in range(len(columns)))
    body = [sep.join(line[i].ljust(widths[i]) for i in range(len(columns))) for line in matrix]
    return "\n".join([header, rule] + body)


def _write_markdown(output_path: Path, question: str, plan: QueryPlan, columns: list[str], rows: list[sqlite3.Row]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    md = [
        "---",
        'title: "Analyse cadastre energetique - requete"',
        'author: "skill analyse-cadastre-energetique"',
        "---",
        "",
        "## Question",
        "",
        question,
        "",
        "## Requete interpretee",
        "",
        f"- intention: {plan.title}",
        f"- sql: `{plan.sql}`",
    ]
    if plan.params:
        md.append(f"- params: `{plan.params}`")

    md.extend(["", "## Resultats", "", "```text", _format_table(columns, rows), "```", ""])
    output_path.write_text("\n".join(md), encoding="utf-8")


def _load_schema_hint(schema_md_path: Path) -> str:
    if not schema_md_path.exists():
        return "Documentation schema indisponible."
    content = schema_md_path.read_text(encoding="utf-8", errors="replace")
    # Extrait une zone concise utile au debug utilisateur.
    marker = "### 4.3.1 Registre énergétique des bâtiments vaudois (RegEner)"
    idx = content.find(marker)
    if idx < 0:
        return "Documentation schema disponible dans les assets du skill."
    snippet = content[idx: idx + 1500]
    return snippet.strip()


def _is_file_older_than_one_year(file_path: Path) -> bool:
    """Verifie si un fichier a plus d'un an."""
    if not file_path.exists():
        return True
    mod_time = file_path.stat().st_mtime
    current_time = time.time()
    one_year_seconds = 365.25 * 24 * 3600
    return (current_time - mod_time) > one_year_seconds


def _looks_like_sqlite(file_path: Path) -> bool:
    """Detecte rapidement un fichier SQLite/GPKG via sa signature binaire."""
    try:
        with file_path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _download_and_extract_gpkg(db_path: Path, url: str) -> None:
    """Telecharge la base depuis l'URL (ZIP ou GPKG direct) et la copie vers db_path."""
    print(f"[INFO] Telechargement de la base de donnees depuis {url}...", file=sys.stderr)
    
    temp_dir = db_path.parent / ".tmp_download"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_download = temp_dir / "download.bin"

    try:
        urllib.request.urlretrieve(url, temp_download)
        print(f"[INFO] Fichier telecharge: {temp_download}", file=sys.stderr)

        gpkg_file: Path | None = None
        if zipfile.is_zipfile(temp_download):
            with zipfile.ZipFile(temp_download, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
                print(f"[INFO] Archive extraite dans {temp_dir}", file=sys.stderr)

            gpkg_files = list(temp_dir.glob("**/*.gpkg"))
            if not gpkg_files:
                raise FileNotFoundError(
                    "Aucun fichier GPKG trouve dans l'archive ZIP. "
                    f"Fichiers trouves: {list(temp_dir.glob('**/*'))}"
                )
            gpkg_file = gpkg_files[0]
            print(f"[INFO] Fichier GPKG trouve dans ZIP: {gpkg_file}", file=sys.stderr)
        elif _looks_like_sqlite(temp_download):
            # Certaines URLs renvoient directement un GPKG (SQLite), sans archive ZIP.
            gpkg_file = temp_download
            print("[INFO] Le telechargement est un GPKG direct (pas de ZIP)", file=sys.stderr)
        else:
            raise ValueError(
                "Le fichier telecharge n'est ni une archive ZIP valide ni un GPKG/SQLite direct."
            )

        # Remplace l'ancienne base par la nouvelle
        if db_path.exists():
            backup_path = db_path.parent / f"{db_path.name}.bak"
            shutil.copy2(db_path, backup_path)
            print(f"[INFO] Ancienne base sauvegardee: {backup_path}", file=sys.stderr)
        
        assert gpkg_file is not None
        shutil.copy2(gpkg_file, db_path)
        print(f"[INFO] Base de donnees mise a jour: {db_path}", file=sys.stderr)
        
    except Exception as exc:
        print(f"[ERREUR] Echec du telechargement/extraction: {exc}", file=sys.stderr)
        raise
    finally:
        # Nettoie les fichiers temporaires
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"[INFO] Fichiers temporaires supprimes", file=sys.stderr)


def _ensure_db_updated(db_path: Path, update_url: str) -> None:
    """Verifie et met a jour la base de donnees si elle n'existe pas ou si elle a plus d'un an."""
    if not db_path.exists():
        print(f"[INFO] Base de donnees introuvable: {db_path}", file=sys.stderr)
        _download_and_extract_gpkg(db_path, update_url)
    elif _is_file_older_than_one_year(db_path):
        print(f"[INFO] Base de donnees trop ancienne (plus d'un an): {db_path}", file=sys.stderr)
        _download_and_extract_gpkg(db_path, update_url)
    else:
        print(f"[INFO] Base de donnees a jour", file=sys.stderr)



def main() -> int:
    parser = argparse.ArgumentParser(description="Interroger la table regener avec du langage naturel.")
    parser.add_argument("--question", required=True, help="Question en langage naturel (ou prefixee par 'sql:').")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Chemin vers la base GPKG/SQLite.")
    parser.add_argument("--schema-md", default=str(DEFAULT_SCHEMA_MD), help="Chemin de la documentation Markdown des colonnes.")
    parser.add_argument("--output", help="Chemin Markdown de sortie (optionnel).")
    parser.add_argument("--json", action="store_true", help="Affiche aussi une sortie JSON sur stdout.")
    parser.add_argument("--show-schema", action="store_true", help="Affiche un extrait de la documentation schema.")
    parser.add_argument("--update-url", default="https://viageo.ch/donnee/telecharger/300579?format=GPKG", 
                        help="URL pour telecharger une nouvelle version de la base (optionnel).")
    parser.add_argument("--skip-update", action="store_true", help="Ignore la verification de mise a jour de la base.")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    schema_md_path = Path(args.schema_md).resolve()

    if not args.skip_update:
        try:
            _ensure_db_updated(db_path, args.update_url)
        except Exception as exc:
            print(f"[AVERTISSEMENT] Impossible de mettre a jour/telecharger la base: {exc}", file=sys.stderr)

    if not db_path.exists():
        print(f"[ERREUR] Base introuvable: {db_path}", file=sys.stderr)
        print(f"[ERREUR] Assurez-vous que --skip-update n'est pas active et que l'URL de telechargement est accessible.", file=sys.stderr)
        return 1

    try:
        plan = _plan_intent(args.question)
    except ValueError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        columns, rows = _execute(conn, plan)
    finally:
        conn.close()

    print(f"Intent: {plan.title}")
    print(_format_table(columns, rows))

    if args.show_schema:
        print("\n--- Extrait schema RegEner ---")
        print(_load_schema_hint(schema_md_path))

    if args.output:
        output_path = Path(args.output).resolve()
        _write_markdown(output_path, args.question, plan, columns, rows)
        print(f"\nSortie Markdown: {output_path}")

    if args.json:
        as_dict = {
            "question": args.question,
            "intent": plan.title,
            "sql": plan.sql,
            "params": plan.params,
            "row_count": len(rows),
            "rows": [dict(r) for r in rows],
        }
        print("\nJSON:")
        print(json.dumps(as_dict, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

