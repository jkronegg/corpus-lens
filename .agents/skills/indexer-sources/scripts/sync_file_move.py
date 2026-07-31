from __future__ import annotations

from typing import Callable


def build_signature_index_from_sources(current_sources: list[dict]) -> dict[str, dict]:
    """Indexe les lignes `source` par signature non vide."""
    by_signature: dict[str, dict] = {}
    for item in current_sources:
        sig = item.get("signature")
        if isinstance(sig, str) and sig:
            by_signature[sig] = item
    return by_signature


def manage_moved_file(
    con,
    file_sig: str, # signature MD5 du fichier
    rel_path: str, # chemin relatif du fichier
    logger: Callable[[str], None] = print,
) -> dict[str, bool | list[str]]:
    """Corrige en base les chemins d'un fichier déplacé à partir de sa signature MD5."""
    normalized_signature = str(file_sig or "").strip()
    normalized_path = str(rel_path or "").strip().replace("\\", "/")
    corrected_childs: list[str] = []

    if not normalized_signature or not normalized_path:
        return {
            "source_found": False,
            "source_document_found": False,
            "corrected_source": False,
            "corrected_source_document": False,
            "corrected_childs": corrected_childs,
        }

    with con:
        source_cursor = con.execute(
            "SELECT count(*) FROM source WHERE signature = ?",
            (normalized_signature,),
        )
        source_found = source_cursor.fetchone()[0] > 0

        source_cursor = con.execute(
            "SELECT count(*) FROM source_document WHERE signature = ?",
            (normalized_signature,),
        )
        source_document_found = source_cursor.fetchone()[0] > 0

        if source_found:
            source_cursor = con.execute(
                "UPDATE source "
                "SET origine = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
                "WHERE signature = ? AND origine != ?",
                (normalized_path, normalized_signature, normalized_path),
            )
            corrected_source = source_cursor.rowcount > 0
        else:
            corrected_source = False

        if source_document_found:
            source_document_cursor = con.execute(
                "UPDATE source_document "
                "SET path = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
                "WHERE signature = ? AND path != ?",
                (normalized_path, normalized_signature, normalized_path),
            )
            corrected_source_document = source_document_cursor.rowcount > 0
        else:
            corrected_source_document = False

    if corrected_source:
        logger(f"[RENAME] correction source via signature: {normalized_path!r}")
    if corrected_source_document:
        logger(
            f"[RENAME] correction source_document via signature: {normalized_path!r}"
        )

    return {
        "source_found": source_found,
        "source_document_found": source_document_found,
        "corrected_source": corrected_source,
        "corrected_source_document": corrected_source_document,
        "corrected_childs": corrected_childs,
    }

