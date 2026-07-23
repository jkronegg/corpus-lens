"""
db.py — Module partagé d'accès à la base SQLite des entités nommées.

Fournit:
  - get_connection()    : connexion SQLite avec WAL + foreign keys
  - list_sources()      : lecture de l'index des sources stocké en base
  - source_exists_by_url() : vérifie si une source existe déjà pour une URL
  - replace_sources()   : remplacement déterministe de l'index des sources
  - upsert_source()     : création ou mise à jour d'une source et de ses documents
  - register_source_document() : helper pour enregistrer un document source (original ou dérivé)
  - upsert_person()     : création ou mise à jour d'une personne
  - add_mention()       : ajout idempotent d'une mention
  - search_person()     : recherche insensible à la casse sur nom et alias
  - list_mentions()     : liste de mentions filtrées
  - export_person()     : export dict complet personne + mentions
  - get_stats()         : statistiques globales
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Chemins par défaut
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[4]  # corpus-lens/
DEFAULT_DB = _REPO_ROOT / "named_entities.sqlite"
DEFAULT_SCHEMA = (
    _REPO_ROOT
    / ".agents"
    / "skills"
    / "manage-named-entities-db"
    / "assets"
    / "schema.sql"
)


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

def get_connection(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Retourne une connexion SQLite avec WAL et foreign keys activés."""
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(con)
    return con


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_schema(con: sqlite3.Connection) -> None:
    """Applique le schéma versionné si nécessaire (création/mise à niveau idempotente)."""
    if not DEFAULT_SCHEMA.exists():
        return

    # Pré-migration: certaines anciennes bases ont les tables mais pas les nouvelles
    # colonnes, ce qui peut faire échouer les CREATE INDEX/VIEW du schéma.
    existing_tables = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    if "source_document" in existing_tables:
        source_document_columns = {
            row[1] for row in con.execute("PRAGMA table_info(source_document)")
        }
        if "signature" not in source_document_columns:
            con.execute(
                "ALTER TABLE source_document "
                "ADD COLUMN signature TEXT"
            )
            _backfill_source_document_signatures(con)
            source_document_columns = {
                row[1] for row in con.execute("PRAGMA table_info(source_document)")
            }
        if "parent_doc_id" not in source_document_columns:
            con.execute(
                "ALTER TABLE source_document "
                "ADD COLUMN parent_doc_id INTEGER REFERENCES source_document(id) ON DELETE SET NULL"
            )

        # Migration schéma: suppression de la colonne legacy `document_kind`.
        if "document_kind" in source_document_columns:
            foreign_keys_was_on = con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            if foreign_keys_was_on:
                con.execute("PRAGMA foreign_keys = OFF")

            con.executescript(
                """
                CREATE TABLE source_document_new (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id     INTEGER NOT NULL
                        REFERENCES source(id) ON DELETE CASCADE,
                    parent_doc_id INTEGER
                        REFERENCES source_document(id) ON DELETE SET NULL,
                    path          TEXT    NOT NULL UNIQUE,
                    signature     TEXT,
                    file_name     TEXT    NOT NULL,
                    relative_path TEXT,
                    author        TEXT    NOT NULL DEFAULT '',
                    ner_status    NUMBER  DEFAULT NULL
                        CHECK (ner_status IN (0, 1, 2))
                );

                INSERT INTO source_document_new (id, source_id, parent_doc_id, path, signature, file_name, relative_path, author, ner_status)
                SELECT id, source_id, parent_doc_id, path, signature, file_name, relative_path, author, ner_status
                FROM source_document;

                DROP TABLE source_document;
                ALTER TABLE source_document_new RENAME TO source_document;
                """
            )

            if foreign_keys_was_on:
                con.execute("PRAGMA foreign_keys = ON")

    if "mention" in existing_tables:
        mention_columns = {row[1] for row in con.execute("PRAGMA table_info(mention)")}
        if "source_document_id" not in mention_columns:
            con.execute(
                "ALTER TABLE mention "
                "ADD COLUMN source_document_id INTEGER REFERENCES source_document(id) ON DELETE CASCADE"
            )

    # Pré-migration critique: sur certaines bases legacy, `source` existe sans
    # `ocr_status`, et/ou avec l'ancien nom `identifiant_technique` au lieu de
    # `signature`. Il faut migrer AVANT d'exécuter schema.sql, sinon les index
    # et vues du schéma peuvent échouer.
    if "source" in existing_tables:
        source_columns = {row[1] for row in con.execute("PRAGMA table_info(source)")}
        if "signature" not in source_columns and "identifiant_technique" in source_columns:
            con.execute(
                "ALTER TABLE source RENAME COLUMN identifiant_technique TO signature"
            )
            source_columns = {row[1] for row in con.execute("PRAGMA table_info(source)")}
        if "ocr_status" not in source_columns:
            con.execute(
                "ALTER TABLE source "
                "ADD COLUMN ocr_status TEXT NOT NULL DEFAULT 'N' "
                "CHECK (ocr_status IN ('P', 'T', 'D', 'F', 'N'))"
            )
            con.execute(
                "UPDATE source "
                "SET ocr_status = CASE "
                "WHEN lower(origine) LIKE '%.pdf' THEN 'P' "
                "WHEN lower(origine) LIKE '%.md' THEN 'N' "
                "ELSE 'N' END "
                "WHERE ocr_status IS NULL OR ocr_status = ''"
            )

    schema_sql = DEFAULT_SCHEMA.read_text(encoding="utf-8")
    con.executescript(schema_sql)

    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_signature ON source(signature)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_document_parent_doc_id "
        "ON source_document(parent_doc_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_document_signature "
        "ON source_document(signature)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_source_ocr_status ON source(ocr_status)"
    )
    con.commit()


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_")


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _default_ocr_status_for_path(path: str) -> str:
    lowered = (path or "").strip().lower()
    if lowered.endswith(".pdf"):
        return "P"
    if lowered.endswith(".md"):
        return "N"
    return "N"


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _compute_document_signature_from_repo_path(path: str) -> str | None:
    normalized = str(path or "").strip().replace("\\", "/")
    if not normalized:
        return None
    absolute_path = _REPO_ROOT / Path(normalized)
    if not absolute_path.exists() or not absolute_path.is_file():
        return None
    return _md5_file(absolute_path)


def _backfill_source_document_signatures(con: sqlite3.Connection) -> int:
    rows = con.execute(
        """
        SELECT id, path
        FROM source_document
        WHERE signature IS NULL OR trim(signature) = ''
        ORDER BY id
        """
    ).fetchall()
    updated = 0
    for row in rows:
        signature = _compute_document_signature_from_repo_path(row["path"])
        if not signature:
            continue
        con.execute(
            "UPDATE source_document SET signature = ? WHERE id = ?",
            (signature, row["id"]),
        )
        updated += 1
    return updated


def _to_repo_rel_posix(path: Path | str) -> str:
    return Path(path).resolve().relative_to(_REPO_ROOT).as_posix()


def _normalize_source_entry(entry: dict) -> dict:
    auteurs = list(entry.get("auteurs") or []) if isinstance(entry.get("auteurs"), list) else []
    periodes = list(entry.get("periodes") or []) if isinstance(entry.get("periodes"), list) else []
    clean_auteurs = [str(a).strip() for a in auteurs if str(a).strip()]
    clean_periodes = [str(p).strip() for p in periodes if str(p).strip()]
    raw_origin = entry.get("path") or entry.get("origine") or ""
    raw_parent = entry.get("parent_path") or ""
    raw_file_name = entry.get("file_name") or ""
    raw_relative_path = entry.get("relative_path") or ""
    origin_or_path = str(raw_origin).strip().replace("\\", "/")
    parent_path = str(raw_parent).strip().replace("\\", "/")
    file_name = str(raw_file_name).strip() or Path(origin_or_path).name
    relative_path = str(raw_relative_path).strip().replace("\\", "/")
    if not relative_path:
        relative_path = "." if not parent_path else file_name
    raw_ner_status = entry.get("ner_status")
    ner_status: int | None
    if raw_ner_status is None:
        ner_status = None
    else:
        ner_status = int(str(raw_ner_status).strip())
        if ner_status not in {0, 1, 2}:
            raise ValueError("ner_status doit être 0, 1, 2 ou None")

    raw_ocr_status = entry.get("ocr_status")
    if raw_ocr_status is None:
        ocr_status = None
    else:
        ocr_status = str(raw_ocr_status).strip().upper()
        if ocr_status not in {"P", "T", "D", "F", "N"}:
            raise ValueError("ocr_status doit être P, T, D, F, N ou None")

    return {
        "signature": str(entry.get("signature") or entry.get("identifiant_technique") or "").strip(),
        "document_signature": str(entry.get("document_signature") or entry.get("source_document_signature") or "").strip(),
        "identifiant_source": str(entry.get("identifiant_source") or "").strip(),
        "titre": str(entry.get("titre") or "").strip(),
        "date_publication": str(entry.get("date_publication") or "0000-00-00").strip() or "0000-00-00",
        "date_consultation": str(entry.get("date_consultation") or "0000-00-00").strip() or "0000-00-00",
        "origine": origin_or_path,
        "auteurs": clean_auteurs,
        "periodes": clean_periodes,
        "ISBN": str(entry.get("ISBN") or "").strip(),
        "ISSN": str(entry.get("ISSN") or "").strip(),
        "DOI": str(entry.get("DOI") or "").strip(),
        "URL": str(entry.get("URL") or entry.get("url") or "").strip(),
        "langues": entry.get("langues"),
        "type_source": str(entry.get("type_source") or "secondaire").strip() or "secondaire",
        "nombre_pages": int(entry.get("nombre_pages", -1) if entry.get("nombre_pages") is not None else -1),
        "categorie": str(entry.get("categorie") or "autre").strip() or "autre",
        "extrait_brut": str(entry.get("extrait_brut") or ""),
        "resume": str(entry.get("resume") or ""),
        "parent_path": parent_path,
        "path": origin_or_path,
        "file_name": file_name,
        "relative_path": relative_path,
        "author": str(entry.get("author") or "").strip(),
        "ner_status": ner_status,
        "ocr_status": ocr_status,
    }


def list_sources(
    con: sqlite3.Connection,
    limit: Optional[int] = None,
    signature: Optional[str] = None,
    url: Optional[str] = None,
    origine: Optional[str] = None,
) -> list[dict]:
    """Liste les sources indexées dans SQLite, triées par signature.

    Les filtres sont cumulables.
    """
    conditions: list[str] = []
    params: list[object] = []

    signature_filter = signature
    if signature_filter:
        conditions.append("signature = ?")
        params.append(signature_filter.strip())

    if url:
        candidate = url.strip()
        if candidate:
            alt = candidate[:-1] if candidate.endswith("/") else f"{candidate}/"
            conditions.append("(url = ? OR url = ?)")
            params.extend([candidate, alt])

    if origine:
        candidate = origine.strip()
        if candidate:
            conditions.append("origine LIKE ?")
            params.append(f"%{candidate}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM source {where_clause} ORDER BY signature"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = con.execute(sql, params).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["auteurs"] = json.loads(item.pop("auteurs_json"))
        item["periodes"] = json.loads(item.pop("periodes_json"))
        item["ISBN"] = item.pop("isbn")
        item["ISSN"] = item.pop("issn")
        item["DOI"] = item.pop("doi")
        item["URL"] = item.pop("url")
        item["ocr_status"] = str(item.get("ocr_status") or "N")
        item.pop("id", None)
        item.pop("created_at", None)
        item.pop("updated_at", None)
        out.append(item)
    return out


def source_exists_by_url(con: sqlite3.Connection, url: str) -> bool:
    """Indique si une source avec cette URL existe déjà dans la base.

    Vérifie d'abord la colonne `url`, puis `origine` (utile pour les collecteurs
    qui stockent l'URL source dans `origine`).
    """
    candidate = str(url or "").strip()
    if not candidate:
        return False

    # Tolère les variations de slash final sans élargir la recherche.
    alt = candidate[:-1] if candidate.endswith("/") else f"{candidate}/"

    row = con.execute(
        """
        SELECT 1
        FROM source
        WHERE url IN (?, ?)
           OR origine IN (?, ?)
        LIMIT 1
        """,
        (candidate, alt, candidate, alt),
    ).fetchone()
    return row is not None


def list_source_documents(
    con: sqlite3.Connection,
    *,
    ner_status: Optional[int] = None,
    source: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Liste les documents indexés avec filtres optionnels sur ner_status et source."""
    conditions: list[str] = []
    params: list[object] = []

    if ner_status is not None:
        conditions.append("sd.ner_status = ?")
        params.append(ner_status)

    if source:
        conditions.append("(sd.path LIKE ? OR s.identifiant_source LIKE ? OR s.titre LIKE ?)")
        pattern = f"%{source.strip()}%"
        params.extend([pattern, pattern, pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = con.execute(
        f"""
        SELECT
            sd.id,
            sd.source_id,
            sd.parent_doc_id,
            sd.path,
            sd.signature,
            sd.file_name,
            sd.relative_path,
            sd.author,
            sd.ner_status,
            s.signature,
            s.identifiant_source,
            s.titre
        FROM source_document sd
        LEFT JOIN source s ON s.id = sd.source_id
        {where_clause}
        ORDER BY sd.path
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def list_sources_for_ocr(
    con: sqlite3.Connection,
    *,
    statuses: tuple[str, ...] = ("P", "F", "T"),
    limit: int | None = None,
) -> list[dict]:
    """Liste les sources PDF originales à retraiter selon leur statut OCR."""
    normalized_statuses = tuple(str(status).strip().upper() for status in statuses if str(status).strip())
    if not normalized_statuses:
        return []

    placeholders = ", ".join("?" for _ in normalized_statuses)
    params: list[object] = list(normalized_statuses)
    sql = f"""
        SELECT s.*, sd.id AS document_id, sd.path AS document_path, sd.ner_status
             , sd.signature AS document_signature
        FROM source s
        JOIN source_document sd ON sd.source_id = s.id
        WHERE sd.parent_doc_id IS NULL
          AND lower(sd.path) LIKE '%.pdf'
          AND s.ocr_status IN ({placeholders})
        ORDER BY sd.path
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    rows = con.execute(sql, params).fetchall()
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["auteurs"] = json.loads(item.pop("auteurs_json"))
        item["periodes"] = json.loads(item.pop("periodes_json"))
        item["ISBN"] = item.pop("isbn")
        item["ISSN"] = item.pop("issn")
        item["DOI"] = item.pop("doi")
        item["URL"] = item.pop("url")
        out.append(item)
    return out


def get_source_with_documents_by_path(con: sqlite3.Connection, path: str) -> Optional[dict]:
    """Retourne une source et son document original à partir d'un path repo-relatif."""
    row = con.execute(
        """
        SELECT
            s.*, sd.id AS document_id, sd.path AS document_path,
            sd.signature AS document_signature,
            sd.file_name AS document_file_name, sd.relative_path AS document_relative_path,
            sd.author AS document_author, sd.ner_status AS document_ner_status,
            sd.parent_doc_id AS document_parent_doc_id
        FROM source_document sd
        JOIN source s ON s.id = sd.source_id
        WHERE sd.path = ?
        LIMIT 1
        """,
        (str(path or "").strip().replace("\\", "/"),),
    ).fetchone()
    if row is None:
        return None

    item = dict(row)
    item["auteurs"] = json.loads(item.pop("auteurs_json"))
    item["periodes"] = json.loads(item.pop("periodes_json"))
    item["ISBN"] = item.pop("isbn")
    item["ISSN"] = item.pop("issn")
    item["DOI"] = item.pop("doi")
    item["URL"] = item.pop("url")
    return item


def update_source_ocr_status(con: sqlite3.Connection, source_id: int, ocr_status: str) -> dict:
    """Met à jour atomiquement le statut OCR d'une source."""
    normalized = str(ocr_status or "").strip().upper()
    if normalized not in {"P", "T", "D", "F", "N"}:
        raise ValueError("ocr_status doit être P, T, D, F ou N")

    with con:
        row = con.execute("SELECT ocr_status FROM source WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            return {"action": "error", "reason": f"Source introuvable: {source_id}", "source_id": source_id}
        con.execute(
            "UPDATE source SET ocr_status = ?, updated_at = ? WHERE id = ?",
            (normalized, _now_iso(), source_id),
        )
    return {"action": "updated", "source_id": source_id, "ocr_status": normalized}


def upsert_source(con: sqlite3.Connection, source: dict) -> dict:
    """Crée/maj une source (parent_path vide) ou un document dérivé (parent_path renseigné)."""
    entry = _normalize_source_entry(source)
    path = entry["path"]
    parent_path = entry["parent_path"]
    effective_ocr_status = entry["ocr_status"] or _default_ocr_status_for_path(path)
    document_signature = entry["document_signature"] or _compute_document_signature_from_repo_path(path)

    if not path:
        return {"action": "error", "reason": "Champ manquant: path/origine", "source_id": None}

    if parent_path:
        if parent_path == path:
            return {
                "action": "error",
                "reason": "Un document dérivé ne peut pas être son propre parent",
                "source_id": None,
            }

        with con:
            parent_doc = con.execute(
                "SELECT id, source_id FROM source_document WHERE path = ? LIMIT 1",
                (parent_path,),
            ).fetchone()
            if parent_doc is None:
                return {
                    "action": "error",
                    "reason": f"Document parent introuvable: {parent_path}",
                    "source_id": None,
                }

            source_id = parent_doc["source_id"]
            parent_doc_id = parent_doc["id"]
            existing_doc = con.execute(
                "SELECT id FROM source_document WHERE path = ? LIMIT 1",
                (path,),
            ).fetchone()

            if existing_doc is None:
                cur = con.execute(
                    """
                    INSERT INTO source_document
                        (source_id, path, signature, file_name, relative_path, author, parent_doc_id, ner_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        path,
                        document_signature,
                        entry["file_name"],
                        entry["relative_path"],
                        entry["author"],
                        parent_doc_id,
                        entry["ner_status"],
                    ),
                )
                document_id = cur.lastrowid
                action = "created"
            else:
                document_id = existing_doc["id"]
                con.execute(
                    """
                    UPDATE source_document
                    SET source_id = ?,
                        signature = ?,
                        file_name = ?,
                        relative_path = ?,
                        author = ?,
                        parent_doc_id = ?,
                        ner_status = ?
                    WHERE id = ?
                    """,
                    (
                        source_id,
                        document_signature,
                        entry["file_name"],
                        entry["relative_path"],
                        entry["author"],
                        parent_doc_id,
                        entry["ner_status"],
                        document_id,
                    ),
                )
                action = "updated"

        return {
            "action": action,
            "source_id": source_id,
            "document_id": document_id,
        }

    required = {
        "signature": entry["signature"],
        "identifiant_source": entry["identifiant_source"],
        "origine": entry["origine"],
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        return {
            "action": "error",
            "reason": f"Champs source manquants: {', '.join(missing)}",
            "source_id": None,
        }

    now = _now_iso()
    # TODO c'est un peu compliqué d'avoir trois identifiants pour la source => à simplifier
    with con:
        existing = con.execute(
            """
            SELECT id
            FROM source
            WHERE signature = ?
               OR identifiant_source = ?
               OR origine = ?
            ORDER BY CASE
                WHEN signature = ? THEN 0
                WHEN identifiant_source = ? THEN 1
                ELSE 2
            END
            LIMIT 1
            """,
            (
                entry["signature"],
                entry["identifiant_source"],
                entry["origine"],
                entry["signature"],
                entry["identifiant_source"],
            ),
        ).fetchone()

        source_id = existing["id"] if existing is not None else None

        for column, value in (
            ("signature", entry["signature"]),
            ("identifiant_source", entry["identifiant_source"]),
            ("origine", entry["origine"]),
        ):
            if source_id is None:
                con.execute(f"DELETE FROM source WHERE {column} = ?", (value,))
            else:
                con.execute(f"DELETE FROM source WHERE {column} = ? AND id != ?", (value, source_id))

        payload = (
            entry["signature"],
            entry["identifiant_source"],
            entry["titre"],
            entry["date_publication"],
            entry["date_consultation"],
            entry["origine"],
            _json_dumps(entry["auteurs"]),
            _json_dumps(entry["periodes"]),
            entry["ISBN"],
            entry["ISSN"],
            entry["DOI"],
            entry["URL"],
            entry["langues"],
            entry["type_source"],
            entry["nombre_pages"],
            entry["categorie"],
            entry["extrait_brut"],
            entry["resume"],
            effective_ocr_status,
        )

        if source_id is None:
            cur = con.execute(
                """
                INSERT INTO source (
                    signature, identifiant_source, titre,
                    date_publication, date_consultation, origine,
                    auteurs_json, periodes_json, isbn, issn, doi, url,
                    langues, type_source, nombre_pages,
                    categorie, extrait_brut, resume, ocr_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload + (now, now),
            )
            source_id = cur.lastrowid
            action = "created"
        else:
            con.execute(
                """
                UPDATE source
                SET signature = ?,
                    identifiant_source = ?,
                    titre = ?,
                    date_publication = ?,
                    date_consultation = ?,
                    origine = ?,
                    auteurs_json = ?,
                    periodes_json = ?,
                    isbn = ?,
                    issn = ?,
                    doi = ?,
                    url = ?,
                    langues = ?,
                    type_source = ?,
                    nombre_pages = ?,
                    categorie = ?,
                    extrait_brut = ?,
                    resume = ?,
                    ocr_status = COALESCE(NULLIF(ocr_status, ''), ?),
                    updated_at = ?
                WHERE id = ?
                """,
                payload[:-1] + (effective_ocr_status, now, source_id),
            )
            action = "updated"

        existing_doc = con.execute(
            "SELECT id FROM source_document WHERE path = ? LIMIT 1",
            (path,),
        ).fetchone()
        if existing_doc is None:
            cur_doc = con.execute(
                """
                INSERT INTO source_document
                    (source_id, path, signature, file_name, relative_path, author, parent_doc_id, ner_status)
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    source_id,
                    path,
                    document_signature,
                    entry["file_name"],
                    entry["relative_path"],
                    entry["author"],
                    entry["ner_status"],
                ),
            )
            document_id = cur_doc.lastrowid
        else:
            document_id = existing_doc["id"]
            con.execute(
                """
                UPDATE source_document
                SET source_id = ?,
                    signature = ?,
                    file_name = ?,
                    relative_path = ?,
                    author = ?,
                    parent_doc_id = NULL,
                    ner_status = ?
                WHERE id = ?
                """,
                (
                    source_id,
                    document_signature,
                    entry["file_name"],
                    entry["relative_path"],
                    entry["author"],
                    entry["ner_status"],
                    document_id,
                ),
            )

    return {
        "action": action,
        "source_id": source_id,
        "document_id": document_id,
    }


def register_source_document(
    con: sqlite3.Connection,
    *,
    origin_path: Path | str,
    identifiant_source: str = "",
    titre: str = "",
    url: str = "",
    auteurs: Optional[list[str]] = None,
    periodes: Optional[list[str]] = None,
    isbn: str = "",
    issn: str = "",
    doi: str = "",
    langues: str | None = None,
    type_source: str = "secondaire",
    nombre_pages: int = -1,
    categorie: str = "autre",
    extrait_brut: str = "",
    resume: str = "",
    date_publication: str = "0000-00-00",
    date_consultation: str | None = None,
    parent_path: Path | str | None = None,
    author: str = "",
    ner_status: Optional[int] = None,
) -> dict:
    """Enregistre un document source original ou dérivé."""
    origin = Path(origin_path).resolve()
    if not origin.exists():
        return {
            "action": "error",
            "reason": f"Fichier source introuvable: {origin}",
            "source_id": None,
        }

    consult_date = (date_consultation or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
    origin_rel = _to_repo_rel_posix(origin)
    parent_rel = _to_repo_rel_posix(parent_path) if parent_path is not None else ""

    if not parent_rel and (not identifiant_source or not titre):
        return {
            "action": "error",
            "reason": "identifiant_source et titre sont obligatoires pour un document original",
            "source_id": None,
        }

    if not parent_rel:
        signature = _md5_file(origin)
    else:
        signature = ""

    entry = {
        "signature": signature,
        "identifiant_source": identifiant_source,
        "titre": titre,
        "date_publication": date_publication,
        "date_consultation": consult_date,
        "origine": origin_rel,
        "auteurs": [str(a).strip() for a in (auteurs or []) if str(a).strip()],
        "periodes": [str(p).strip() for p in (periodes or []) if str(p).strip()],
        "ISBN": isbn,
        "ISSN": issn,
        "DOI": doi,
        "URL": url,
        "langues": langues,
        "type_source": type_source,
        "nombre_pages": nombre_pages,
        "categorie": categorie,
        "extrait_brut": extrait_brut,
        "resume": resume,
        "parent_path": parent_rel,
        "file_name": origin.name,
        "relative_path": "." if not parent_rel else origin.name,
        "author": author,
        "ner_status": ner_status,
        "ocr_status": None if parent_rel else _default_ocr_status_for_path(origin_rel),
    }
    return upsert_source(con, entry)



def replace_sources(con: sqlite3.Connection, sources: list[dict]) -> dict:
    """Remplace de façon déterministe l'index des sources par les lignes fournies."""
    warnings.warn(
        "replace_sources() est deprecated: préférer upsert_source() pour préserver les colonnes OCR et éviter une reconstruction globale opaque.",
        DeprecationWarning,
        stacklevel=2,
    )
    existing_statuses_by_key: dict[str, str] = {}
    for row in con.execute("SELECT signature, identifiant_source, origine, ocr_status FROM source"):
        status = str(row["ocr_status"] or "").strip().upper() or "N"
        for key in (row["signature"], row["identifiant_source"], row["origine"]):
            if key:
                existing_statuses_by_key[str(key)] = status

    normalized = []
    seen_ids: set[str] = set()
    for raw in sources:
        entry = _normalize_source_entry(raw)
        entry["ocr_status"] = (
            entry["ocr_status"]
            or existing_statuses_by_key.get(entry["signature"])
            or existing_statuses_by_key.get(entry["identifiant_source"])
            or existing_statuses_by_key.get(entry["origine"])
            or _default_ocr_status_for_path(entry["origine"])
        )
        signature = entry["signature"]
        if not signature or signature in seen_ids:
            continue
        seen_ids.add(signature)
        normalized.append(entry)

    normalized.sort(key=lambda item: item["signature"])

    # Garantit l'unicité de identifiant_source de façon déterministe.
    used_identifiant_source: set[str] = set()
    for entry in normalized:
        base = str(entry.get("identifiant_source") or "").strip()
        if not base:
            base = entry["signature"]

        candidate = base
        index = 2
        while candidate in used_identifiant_source:
            candidate = f"{base}-{index:02d}"
            index += 1

        entry["identifiant_source"] = candidate
        used_identifiant_source.add(candidate)

    now = _now_iso()
    with con:
        # Remplacement total: purge d'abord pour éviter les conflits d'unicité
        # transitoires sur identifiant_source/origine pendant la reconstruction.
        con.execute("DELETE FROM source_document")
        con.execute("DELETE FROM source")

        for entry in normalized:
            con.execute(
                """
                INSERT INTO source (
                    signature, identifiant_source, titre,
                    date_publication, date_consultation, origine,
                    auteurs_json, periodes_json, isbn, issn, doi, url,
                    langues, type_source, nombre_pages,
                    categorie, extrait_brut, resume, ocr_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["signature"],
                    entry["identifiant_source"],
                    entry["titre"],
                    entry["date_publication"],
                    entry["date_consultation"],
                    entry["origine"],
                    _json_dumps(entry["auteurs"]),
                    _json_dumps(entry["periodes"]),
                    entry["ISBN"],
                    entry["ISSN"],
                    entry["DOI"],
                    entry["URL"],
                    entry["langues"],
                    entry["type_source"],
                    entry["nombre_pages"],
                    entry["categorie"],
                    entry["extrait_brut"],
                    entry["resume"],
                    entry["ocr_status"],
                    now,
                    now,
                ),
            )

        signature_to_id = {
            row["signature"]: row["id"]
            for row in con.execute("SELECT id, signature FROM source")
        }

        documents_count = 0
        for entry in normalized:
            source_id = signature_to_id[entry["signature"]]
            origin_path = str(entry["origine"]).strip().replace("\\", "/")
            if not origin_path:
                continue
            con.execute(
                """
                INSERT INTO source_document
                    (source_id, path, signature, file_name, relative_path, author, parent_doc_id, ner_status)
                VALUES (?, ?, ?, ?, '.', '', NULL, ?)
                """,
                (
                    source_id,
                    origin_path,
                    entry.get("document_signature") or _compute_document_signature_from_repo_path(origin_path),
                    Path(origin_path).name,
                    entry["ner_status"],
                ),
            )
            documents_count += 1

    return {
        "action": "replaced",
        "sources_count": len(normalized),
        "documents_count": documents_count,
    }


# ---------------------------------------------------------------------------
# Opérations sur les personnes
# ---------------------------------------------------------------------------

def upsert_person(
    con: sqlite3.Connection,
    key: str,
    display_name: str,
    aliases: Optional[list[str]] = None,
) -> dict:
    """
    Insère ou met à jour une personne.
    Retourne {"action": "created"|"updated", "person_id": int, "key": str}.
    """
    key = _normalize_key(key)
    aliases_json = json.dumps(aliases or [], ensure_ascii=False)
    now = _now_iso()

    cur = con.execute("SELECT id FROM person WHERE key = ?", (key,))
    row = cur.fetchone()

    if row is None:
        # Création dans named_entity puis person
        cur = con.execute(
            "INSERT INTO named_entity (key, entity_type, display_name, created_at) "
            "VALUES (?, 'person', ?, ?)",
            (key, display_name, now),
        )
        entity_id = cur.lastrowid
        cur = con.execute(
            "INSERT INTO person (entity_id, key, display_name, aliases_names, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (entity_id, key, display_name, aliases_json, now),
        )
        person_id = cur.lastrowid
        con.commit()
        return {"action": "created", "person_id": person_id, "key": key}
    else:
        person_id = row["id"]
        con.execute(
            "UPDATE person SET display_name = ?, aliases_names = ? WHERE key = ?",
            (display_name, aliases_json, key),
        )
        con.execute(
            "UPDATE named_entity SET display_name = ? WHERE key = ?",
            (display_name, key),
        )
        con.commit()
        return {"action": "updated", "person_id": person_id, "key": key}


# ---------------------------------------------------------------------------
# Opérations sur les mentions
# ---------------------------------------------------------------------------

def add_mention(
    con: sqlite3.Connection,
    person_key: str,
    source: str,
    page: int,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    quote: Optional[str] = None,
    event_date: Optional[str] = None,
    extractor: str = "manual",
    confidence: Optional[float] = None,
) -> dict:
    """
    Ajoute une mention (idempotent via contrainte UNIQUE).
    Retourne {"action": "created"|"skipped", "mention_id": int|None, "reason": str|None}.
    """
    person_key = _normalize_key(person_key)
    cur = con.execute(
        "SELECT p.entity_id, p.id FROM person p WHERE p.key = ?", (person_key,)
    )
    row = cur.fetchone()
    if row is None:
        return {
            "action": "error",
            "mention_id": None,
            "reason": f"Personne introuvable : {person_key!r}",
        }

    entity_id = row["entity_id"]
    now = _now_iso()
    source_document_id_row = con.execute(
        "SELECT id FROM source_document WHERE path = ?",
        (source,),
    ).fetchone()
    source_document_id = source_document_id_row["id"] if source_document_id_row else None

    # Lookup explicite avant insertion (NULL != NULL en SQL, la contrainte UNIQUE
    # ne suffit pas quand line_start / line_end / quote peuvent être NULL).
    existing = con.execute(
        """
        SELECT id FROM mention
        WHERE entity_id  = ?
          AND source     = ?
          AND page       = ?
          AND (line_start IS ? OR line_start = ?)
          AND (line_end   IS ? OR line_end   = ?)
          AND (quote      IS ? OR quote      = ?)
        LIMIT 1
        """,
        (entity_id, source, page,
         line_start, line_start,
         line_end, line_end,
         quote, quote),
    ).fetchone()
    if existing:
        return {
            "action": "skipped",
            "mention_id": existing["id"],
            "reason": "Mention identique déjà présente.",
        }

    cur = con.execute(
        """
        INSERT INTO mention
            (entity_id, source, source_document_id, page, line_start, line_end, quote,
             event_date, creation_date, extractor, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, source, source_document_id, page, line_start, line_end, quote,
         event_date, now, extractor, confidence),
    )
    con.commit()
    return {"action": "created", "mention_id": cur.lastrowid, "reason": None}


def source_has_mentions(con: sqlite3.Connection, source: str) -> bool:
    """Indique si une source a déjà été traitée (au moins une mention présente)."""
    row = con.execute(
        "SELECT 1 FROM mention WHERE source = ? LIMIT 1",
        (source,),
    ).fetchone()
    return row is not None


def delete_mentions_for_source(con: sqlite3.Connection, source: str) -> int:
    """
    Supprime toutes les mentions associées à une source.
    Retourne le nombre de mentions supprimées.
    """
    with con:
        cursor = con.execute(
            "DELETE FROM mention WHERE source = ?",
            (source,),
        )
        deleted_count = cursor.rowcount
    return deleted_count


def reset_ner_analysis(con: sqlite3.Connection) -> dict:
    """Remet à zéro l'analyse NER: purge mention/person/named_entity et repasse ner_status de 2 à 1."""
    with con:
        deleted_mentions = con.execute("DELETE FROM mention").rowcount
        deleted_persons = con.execute("DELETE FROM person").rowcount
        deleted_named_entities = con.execute("DELETE FROM named_entity").rowcount
        updated_documents = con.execute(
            "UPDATE source_document SET ner_status = 1 WHERE ner_status = 2"
        ).rowcount

    return {
        "action": "reset_ner_analysis",
        "deleted_mentions": deleted_mentions,
        "deleted_persons": deleted_persons,
        "deleted_named_entities": deleted_named_entities,
        "updated_source_documents": updated_documents,
    }


# ---------------------------------------------------------------------------
# Recherche de personnes
# ---------------------------------------------------------------------------

def search_person(
    con: sqlite3.Connection,
    name: str,
    limit: int = 10,
) -> list[dict]:
    """
    Recherche une personne par nom ou alias (LIKE insensible à la casse).
    Retourne une liste de dicts avec mention_count.
    """
    pattern = f"%{name.strip()}%"
    rows = con.execute(
        """
        SELECT
            p.id            AS person_id,
            p.key,
            p.display_name,
            p.aliases_names,
            COUNT(m.id)     AS mention_count
        FROM person p
        LEFT JOIN mention m ON m.entity_id = p.entity_id
        WHERE p.display_name LIKE ? COLLATE NOCASE
           OR p.aliases_names LIKE ? COLLATE NOCASE
           OR p.key LIKE ? COLLATE NOCASE
        GROUP BY p.id
        ORDER BY mention_count DESC, p.display_name
        LIMIT ?
        """,
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Liste des mentions
# ---------------------------------------------------------------------------

def list_mentions(
    con: sqlite3.Connection,
    person_key: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Liste les mentions filtrées par personne et/ou source.
    """
    conditions = []
    params: list = []

    if person_key:
        conditions.append("vm.person_key = ?")
        params.append(_normalize_key(person_key))
    if source:
        conditions.append("vm.source LIKE ?")
        params.append(f"%{source}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    rows = con.execute(
        f"""
        SELECT * FROM v_person_mentions vm
        {where}
        ORDER BY vm.source, vm.page, vm.line_start
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Export personne
# ---------------------------------------------------------------------------

def export_person(con: sqlite3.Connection, person_key: str) -> Optional[dict]:
    """
    Exporte une personne avec toutes ses mentions.
    Retourne None si introuvable.
    """
    person_key = _normalize_key(person_key)
    row = con.execute(
        "SELECT * FROM person WHERE key = ?", (person_key,)
    ).fetchone()
    if row is None:
        return None

    person = dict(row)
    person["aliases_names"] = json.loads(person["aliases_names"])

    mentions = con.execute(
        """
        SELECT m.id, m.source, m.page, m.line_start, m.line_end,
               m.quote, m.event_date, m.creation_date, m.extractor, m.confidence
        FROM mention m
        WHERE m.entity_id = ?
        ORDER BY m.source, m.page, m.line_start
        """,
        (person["entity_id"],),
    ).fetchall()
    person["mentions"] = [dict(m) for m in mentions]
    person["mention_count"] = len(person["mentions"])
    return person


# ---------------------------------------------------------------------------
# Fusion de personnes
# ---------------------------------------------------------------------------

def merge_persons(
    con: sqlite3.Connection,
    source_key: str,
    target_key: str,
) -> dict:
    """
    Fusionne la personne `source_key` dans `target_key`.

    Opérations :
    - Transfère toutes les mentions de source vers target
    - Ajoute display_name et aliases de source dans aliases_names de target
    - Supprime la personne source (cascade sur named_entity)

    Retourne {"action": "merged", "mentions_moved": int, "aliases_added": list}
             ou {"action": "error", "reason": str}
    """
    source_key = _normalize_key(source_key)
    target_key = _normalize_key(target_key)

    if source_key == target_key:
        return {"action": "error", "reason": "Source et cible identiques."}

    src = con.execute(
        "SELECT p.id, p.entity_id, p.display_name, p.aliases_names "
        "FROM person p WHERE p.key = ?", (source_key,)
    ).fetchone()
    if src is None:
        return {"action": "error", "reason": f"Personne source introuvable : {source_key!r}"}

    tgt = con.execute(
        "SELECT p.id, p.entity_id, p.display_name, p.aliases_names "
        "FROM person p WHERE p.key = ?", (target_key,)
    ).fetchone()
    if tgt is None:
        return {"action": "error", "reason": f"Personne cible introuvable : {target_key!r}"}

    src_entity_id = src["entity_id"]
    tgt_entity_id = tgt["entity_id"]

    # 1. Transférer les mentions
    cur = con.execute(
        "UPDATE mention SET entity_id = ? WHERE entity_id = ?",
        (tgt_entity_id, src_entity_id),
    )
    mentions_moved = cur.rowcount

    # 2. Enrichir les aliases de la cible
    tgt_aliases: list = json.loads(tgt["aliases_names"])
    src_aliases: list = json.loads(src["aliases_names"])
    # Ajoute display_name source + tous ses aliases (sans doublons)
    new_aliases = list(tgt_aliases)
    for name in [src["display_name"]] + src_aliases:
        if name and name not in new_aliases and name != tgt["display_name"]:
            new_aliases.append(name)
    aliases_added = [a for a in new_aliases if a not in tgt_aliases]

    con.execute(
        "UPDATE person SET aliases_names = ? WHERE key = ?",
        (json.dumps(new_aliases, ensure_ascii=False), target_key),
    )

    # 3. Supprimer la personne source (cascade sur named_entity → mention déjà migrée)
    con.execute("DELETE FROM person WHERE key = ?", (source_key,))
    con.execute("DELETE FROM named_entity WHERE key = ?", (source_key,))

    con.commit()
    return {
        "action": "merged",
        "source": source_key,
        "target": target_key,
        "mentions_moved": mentions_moved,
        "aliases_added": aliases_added,
    }




def get_stats(con: sqlite3.Connection) -> dict:
    """Retourne des statistiques globales sur la base."""
    persons_count = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    mentions_count = con.execute("SELECT COUNT(*) FROM mention").fetchone()[0]
    indexed_sources_count = con.execute("SELECT COUNT(*) FROM source").fetchone()[0]
    source_documents_count = con.execute("SELECT COUNT(*) FROM source_document").fetchone()[0]
    mentioned_source_paths_count = con.execute("SELECT COUNT(DISTINCT source) FROM mention").fetchone()[0]

    extractor_rows = con.execute(
        "SELECT extractor, COUNT(*) AS cnt FROM mention GROUP BY extractor ORDER BY cnt DESC"
    ).fetchall()
    extractors = {r["extractor"]: r["cnt"] for r in extractor_rows}

    top_persons = con.execute(
        """
        SELECT p.display_name, p.key, COUNT(m.id) AS cnt
        FROM person p
        LEFT JOIN mention m ON m.entity_id = p.entity_id
        GROUP BY p.id
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()

    return {
        "persons": persons_count,
        "mentions": mentions_count,
        "sources": indexed_sources_count,
        "source_documents": source_documents_count,
        "mentioned_source_paths": mentioned_source_paths_count,
        "extractors": extractors,
        "top_persons": [dict(r) for r in top_persons],
    }

