#!/usr/bin/env python3
"""
init_db.py — Initialise ou met à niveau la base de données SQLite du projet.

Le schéma est versionné dans ce skill (.agents/skills/manage-named-entities-db/assets/schema.sql).
La base de données est placée à la racine du projet sous named_entities.sqlite.

Usage:
    python -u ".agents/skills/manage-named-entities-db/scripts/init_db.py"
    python -u ".agents/skills/manage-named-entities-db/scripts/init_db.py" --db named_entities.sqlite
    python -u ".agents/skills/manage-named-entities-db/scripts/init_db.py" --force   # recrée la DB si elle existe
"""

import argparse
import sqlite3
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Chemins par défaut
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).parent.resolve()
SKILL_DIR   = SCRIPT_DIR.parent                             # manage-named-entities-db/
REPO_ROOT   = SKILL_DIR.parents[2]                          # corpus-lens/
SCHEMA_FILE = SKILL_DIR / "assets" / "schema.sql"          # versionné dans le skill
DEFAULT_DB  = REPO_ROOT / "named_entities.sqlite"


def init_db(db_path: Path, force: bool = False) -> None:
    """Crée ou vérifie la base de données à partir de schema.sql."""

    if db_path.exists():
        if force:
            print(f"[init_db] --force: suppression de {db_path}")
            db_path.unlink()
        else:
            print(f"[init_db] La base existe déjà : {db_path}")
            print("[init_db] Mise à niveau idempotente à partir du schéma versionné...")
            con = sqlite3.connect(db_path)
            try:
                con.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
                con.commit()
                _verify(con)
            finally:
                con.close()
            return

    if not SCHEMA_FILE.exists():
        print(f"[init_db] ERREUR : schéma introuvable : {SCHEMA_FILE}", file=sys.stderr)
        sys.exit(1)

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(schema_sql)
        con.commit()
        print(f"[init_db] Base créée   : {db_path}")
        print(f"[init_db] Schéma source: {SCHEMA_FILE}")
        _verify(con)
    finally:
        con.close()


def _verify(db_or_path) -> None:
    """Affiche les tables, index et vues présents dans la base."""
    if isinstance(db_or_path, Path):
        con = sqlite3.connect(db_or_path)
        close_after = True
    else:
        con = db_or_path
        close_after = False

    cur = con.execute(
        "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','view') "
        "ORDER BY type, name"
    )
    rows = cur.fetchall()
    print("[init_db] Objets présents dans la base :")
    for kind, name in rows:
        print(f"  {kind:<8} {name}")

    if close_after:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialise la base SQLite des entités nommées."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Chemin vers la base SQLite (défaut: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Supprime et recrée la base si elle existe déjà.",
    )
    args = parser.parse_args()
    init_db(args.db, force=args.force)


if __name__ == "__main__":
    main()

