import subprocess
import sys
from pathlib import Path

from index_lock import acquire_index_lock, release_index_lock
from sync_file_delete import manage_deleted_files
from sync_file_move import manage_moved_file
from sync_file_add import add_file, is_mostly_french_markdown
from corpus_lens_files import md5_file, to_rel

ROOT = Path(__file__).resolve().parents[4]
SOURCES_DIR = ROOT / "sources"
IGNORED_FILENAMES = {
    "auteurs.json"
}
LOCK_FILE_PREFIXES = ("~$",)

NAMED_ENTITIES_DB_SCRIPTS_DIR = (
    ROOT / ".agents" / "skills" / "manage-named-entities-db" / "scripts"
)
if str(NAMED_ENTITIES_DB_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(NAMED_ENTITIES_DB_SCRIPTS_DIR))
from db import (
    get_connection,
    _ensure_schema
)

NER_EXTRACT_SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "manage-named-entities-db"
    / "scripts"
    / "extract_entities_spacy.py"
)
NER_GLOBAL_LOG_FILE = ROOT / "indexation_sources.log"


def _sync_existing_document_by_path(con, *, source_path: Path, rel_path: str, file_sig: str) -> bool:
    """Met à jour un document existant (même path) et retourne True si déjà connu."""
    row = con.execute(
        "SELECT id, source_id, signature, ner_status FROM source_document WHERE path = ? LIMIT 1",
        (rel_path,),
    ).fetchone()
    if row is None:
        return False

    old_signature = str(row["signature"] or "").strip()
    if old_signature == file_sig:
        return True

    source_document_id = int(row["id"])
    source_id = int(row["source_id"])
    if source_path.suffix.lower() == ".md":
        is_french = is_mostly_french_markdown(source_path)
        previous_status = row["ner_status"]
        ner_status = 1 if is_french or previous_status in {1, 2} else 0
    else:
        ner_status = 0
    now_expr = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"

    with con:
        con.execute(
            f"UPDATE source_document "
            f"SET signature = ?, ner_status = ?, updated_at = {now_expr} "
            "WHERE id = ?",
            (file_sig, ner_status, source_document_id),
        )
        con.execute(
            f"UPDATE source "
            f"SET signature = ?, updated_at = {now_expr} "
            "WHERE id = ? AND origine = ?",
            (file_sig, source_id, rel_path),
        )
        # Le contenu ayant changé, les anciennes mentions ne sont plus valides.
        con.execute(
            "DELETE FROM mention WHERE source_document_id = ? OR source = ?",
            (source_document_id, rel_path),
        )

    print(f"[UPDATE] contenu modifié, signature + NER reset: {rel_path}")
    return True

def run_pdf_extraction_batch() -> bool:
    """Execute batch PDF extraction script and return True if successful."""
    extract_script = (
        ROOT
        / ".agents"
        / "skills"
        / "extract-pdf-to-md-all-sources"
        / "scripts"
        / "extract_pdf_to_md_all_sources.py"
    )
    if not extract_script.exists():
        print(f"[WARN] script PDF extraction introuvable, ignoré: {extract_script}")
        return True  # Ne pas bloquer si le script n'existe pas

    # start the PDF to Markdown generation (no need to display something because the progression bar is enough)
    cmd = [sys.executable, "-u", str(extract_script)]
    result = subprocess.run(cmd, check=False)
    
    if result.returncode != 0:
        print(f"[WARN] extraction batch échouée (code {result.returncode}).")
        return False
    
    return True


def run_named_entities_extraction_batch() -> bool:
    """Lance le batch NER via extract_entities_spacy.py."""
    if not NER_EXTRACT_SCRIPT.exists():
        print(f"[WARN] script NER introuvable, extraction ignorée: {NER_EXTRACT_SCRIPT}")
        return True

    cmd = [
        sys.executable,
        "-u",
        str(NER_EXTRACT_SCRIPT),
        "--batch-from-db",
        "--log-file",
        str(NER_GLOBAL_LOG_FILE),
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[WARN] extraction batch NER échouée (code {result.returncode}).")
        return False
    return True


def main() -> None:
    # Nouveau dépôt sans sources: comportement normal, on sort sans erreur.
    if not SOURCES_DIR.exists():
        print(f"[INFO] aucun répertoire sources détecté ({SOURCES_DIR}); rien à indexer.")
        return

    lock_handle = None
    lock_owner: dict | None = None
    con = None
    try:

        # 1) Lock pour éviter des traitements en parallèle
        lock_handle, lock_message, lock_owner = acquire_index_lock(script_path=Path(__file__).resolve())
        print(f"[INFO] {lock_message}")
        if lock_handle is None:
            return

        # 2) Inventaire: lister les fichiers candidats du répertoire sources.
        all_files = sorted(p for p in SOURCES_DIR.rglob("*") if p.is_file())
        candidate_files: list[Path] = []
        for file_path in all_files:
            if file_path.name in IGNORED_FILENAMES:
                continue
            if file_path.name.startswith(LOCK_FILE_PREFIXES):
                continue
            candidate_files.append(file_path)
        seen_signatures: set[str] = set() # ensemble de toutes les signatures des fichiers du répertoire `sources`, à l'exception des fichiers ignorés

        # 3) Pour chaque fichier: MD5 + détection déplacement/ajout.
        con = get_connection()
        _ensure_schema(con)
        for source_path in sorted(candidate_files, key=lambda p: to_rel(p)):
            rel_path = to_rel(source_path)

            # Étape 1: calculer la signature du fichier (base de la détection de renommage/déplacement)
            file_sig = md5_file(source_path)
            seen_signatures.add(file_sig)

            # Étape 2: fichier déjà indexé au même chemin -> ne traiter que s'il a changé.
            if _sync_existing_document_by_path(
                con,
                source_path=source_path,
                rel_path=rel_path,
                file_sig=file_sig,
            ):
                continue

            # Étape 3: corriger la base de données si le fichier a été déplacé
            move_result = manage_moved_file(
                con,
                file_sig=file_sig,
                rel_path=rel_path,
            )

            # Étape 4: ajout du fichier s'il n'est pas encore en base de données
            if not(move_result["source_found"] or move_result["source_document_found"]):
                add_file(
                    con,
                    source_path=source_path,
                    file_sig=file_sig,
                )

        # 4) Supprimer les documents absents du scan courant via `source_document.signature`.
        manage_deleted_files(
            con,
            retained_signatures=seen_signatures,
        )

        # 5) Extraction batch des PDFs: après la synchronisation SQLite, les PDF disposent d'un ocr_status.
        # Le batch OCR sélectionne les originaux P/F/T depuis la base.
        if not run_pdf_extraction_batch():
            return

        # 6) NER batch pilotee par la table source_document (ner_status = 1).
        if not run_named_entities_extraction_batch():
            return

    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
        if lock_handle is not None:
            release_index_lock(lock_handle, owner=lock_owner)


if __name__ == "__main__":
    main()
