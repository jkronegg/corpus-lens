from __future__ import annotations

from typing import Callable


def delete_orphaned_named_entities(con) -> dict[str, int]:
    """Supprime en cascade les entités nommées inutilisées."""

    # Supprimer les person non utilisées dans des mentions
    deleted_person = con.execute(
        """
        DELETE FROM person
        WHERE NOT EXISTS (
            SELECT 1
            FROM mention m
            WHERE m.entity_id = person.entity_id
        )
        """
    )

    # Supprimer les named_entity non utilisées dans des mentions
    deleted_named_entity = con.execute(
        """
        DELETE FROM named_entity
        WHERE NOT EXISTS (
            SELECT 1
            FROM mention m
            WHERE m.entity_id = named_entity.id
        )
        """
    )
    return {
        "deleted_person_count": deleted_person.rowcount,
        "deleted_named_entity_count": deleted_named_entity.rowcount,
    }


def manage_deleted_files(
    con,
    *,
    retained_signatures: set[str] | None = None,
    logger: Callable[[str], None] = print,
) -> dict[str, int]:
    """Synchronise les suppressions en base uniquement a partir des signatures retenues."""
    if retained_signatures is None:
        raise ValueError("retained_signatures est requis pour la synchronisation par signature")

    retained_signatures_normalized = sorted({
        str(sig).strip()
        for sig in retained_signatures
        if str(sig).strip()
    })

    if retained_signatures_normalized:
        placeholders = ", ".join("?" for _ in retained_signatures_normalized)
        where_clause = f"TRIM(signature) NOT IN ({placeholders})"
        params = tuple(retained_signatures_normalized)
    else:
        where_clause = "1 = 1"
        params = ()

    # Suppression dans la table `source`
    orphan_sources = con.execute(
        f"SELECT origine, signature FROM source WHERE {where_clause} ORDER BY origine",
        params,
    ).fetchall()
    for row in orphan_sources:
        logger(f"[DELETE][source] {row['origine']} ({row['signature']})")
    con.execute(f"DELETE FROM source WHERE {where_clause}", params)
    # Note: delete cascade source -> source_document -> mention

    # Suppression dans la table `source_document` et cascade sur mentions et entités
    orphan_documents = con.execute(
        f"SELECT id, path, signature FROM source_document WHERE {where_clause} ORDER BY path",
        params,
    ).fetchall()
    for row in orphan_documents:
        logger(f"[DELETE][source_document] {row['path']} ({row['signature']})")
    con.execute(f"DELETE FROM source_document WHERE {where_clause}", params)

    delete_orphaned_named_entities(con)

    con.commit()
    return {
        "deleted_source": len(orphan_sources),
        "deleted_source_document": len(orphan_documents+orphan_sources), # il y a un delete cascade de source -> source_document
    }


