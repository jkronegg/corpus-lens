#!/usr/bin/env python3
"""
manage_named_entities_db.py — Point d'entrée du skill manage-named-entities-db.

Usage:
    python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" <sous-commande> [options]

Sous-commandes:
    upsert-person   Ajoute ou met à jour une personne
    add-mention     Ajoute une mention (idempotent)
    search-person   Recherche une personne par nom ou alias
    list-mentions   Liste les mentions d'une personne ou d'une source
    list-sources    Liste les sources indexées dans SQLite
    list-source-documents Liste les documents indexés dans source_document
    upsert-source   Crée ou met à jour une source (ou un document dérivé)
    stats           Statistiques globales sur la base
    export-person   Export JSON d'une personne avec ses mentions
    merge-persons   Fusionne deux personnes (transfère mentions + aliases)
    reset-ner-analysis Réinitialise l'analyse NER (mentions + statuts)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import du module partagé (même répertoire)
sys.path.insert(0, str(Path(__file__).parent))
import db as _db


def _out(data: dict | list) -> None:
    """Émet le résultat JSON sur stdout."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Sous-commandes
# ---------------------------------------------------------------------------

def cmd_upsert_person(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    result = _db.upsert_person(
        con,
        key=args.key,
        display_name=args.display_name,
        aliases=args.aliases or [],
    )
    _out(result)


def cmd_add_mention(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    result = _db.add_mention(
        con,
        person_key=args.person_key,
        source=args.source,
        page=args.page,
        line_start=args.line_start,
        line_end=args.line_end,
        quote=args.quote,
        event_date=args.event_date,
        extractor=args.extractor,
        confidence=args.confidence,
    )
    _out(result)


def cmd_search_person(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    results = _db.search_person(con, name=args.name, limit=args.limit)
    _out({"results": results, "count": len(results)})


def cmd_list_mentions(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    mentions = _db.list_mentions(
        con,
        person_key=args.person_key,
        source=args.source,
        limit=args.limit,
    )
    _out({"mentions": mentions, "count": len(mentions)})


def cmd_stats(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    _out(_db.get_stats(con))


def cmd_list_sources(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    sources = _db.list_sources(
        con,
        limit=args.limit,
        identifiant_technique=args.identifiant_technique,
        url=args.url,
        origine=args.origine,
    )
    _out({"sources": sources, "count": len(sources)})


def cmd_list_source_documents(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    documents = _db.list_source_documents(
        con,
        ner_status=args.ner_status,
        source=args.source,
        limit=args.limit,
    )
    _out({"source_documents": documents, "count": len(documents)})


def cmd_export_person(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    data = _db.export_person(con, person_key=args.person_key)
    if data is None:
        _out({"found": False, "person_key": args.person_key})
        sys.exit(1)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[export-person] Exporté : {out_path}", file=sys.stderr)
    else:
        _out(data)


def cmd_merge_persons(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    result = _db.merge_persons(con, source_key=args.source_key, target_key=args.target_key)
    _out(result)
    if result["action"] == "error":
        sys.exit(1)


def cmd_reset_ner_analysis(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    result = _db.reset_ner_analysis(con)
    _out(result)


def cmd_upsert_source(args: argparse.Namespace) -> None:
    con = _db.get_connection(args.db)
    source = {
        "identifiant_technique": args.identifiant_technique or "",
        "identifiant_source": args.identifiant_source or "",
        "titre": args.titre or "",
        "date_publication": args.date_publication or "0000-00-00",
        "date_consultation": args.date_consultation or "0000-00-00",
        "origine": args.origine or "",
        "path": args.origine or "",
        "auteurs": args.auteurs or [],
        "periodes": args.periodes or [],
        "ISBN": args.isbn or "",
        "ISSN": args.issn or "",
        "DOI": args.doi or "",
        "URL": args.url or "",
        "langues": args.langues or None,
        "pertinence": args.pertinence,
        "type_source": args.type_source or "secondaire",
        "lisible": args.lisible,
        "nombre_pages": args.nombre_pages,
        "categorie": args.categorie or "autre",
        "extrait_brut": args.extrait_brut or "",
        "resume": args.resume or "",
        "parent_path": args.parent_path or "",
        "file_name": args.file_name or "",
        "relative_path": args.relative_path or "",
        "author": args.author or "",
        "ner_status": args.ner_status,
    }
    result = _db.upsert_source(con, source)
    _out(result)


# ---------------------------------------------------------------------------
# Parseur principal
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_named_entities_db.py",
        description="Gestion de la base SQLite des entités nommées.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=_db.DEFAULT_DB,
        help=f"Chemin vers la base SQLite (défaut: {_db.DEFAULT_DB})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ---- upsert-person ----
    p_up = sub.add_parser("upsert-person", help="Ajoute ou met à jour une personne.")
    p_up.add_argument("--key", required=True, help="Clé métier stable (ex. karl_egli_1865)")
    p_up.add_argument("--display-name", required=True, dest="display_name",
                      help="Nom affiché (ex. 'Karl Egli')")
    p_up.add_argument("--aliases", nargs="*", default=[],
                      help="Alias supplémentaires (ex. 'Egli, Karl' 'Colonel Egli')")

    # ---- add-mention ----
    p_am = sub.add_parser("add-mention", help="Ajoute une mention (idempotent).")
    p_am.add_argument("--person-key", required=True, dest="person_key",
                      help="Clé métier de la personne")
    p_am.add_argument("--source", required=True,
                      help="Chemin relatif du fichier source depuis sources/")
    p_am.add_argument("--page", required=True, type=int, help="Numéro de page (## Page X)")
    p_am.add_argument("--line-start", dest="line_start", type=int, default=None)
    p_am.add_argument("--line-end", dest="line_end", type=int, default=None)
    p_am.add_argument("--quote", default=None, help="Extrait de texte")
    p_am.add_argument("--event-date", dest="event_date", default=None,
                      help="Date contextuelle ISO 8601 (ex. 1916-01-11)")
    p_am.add_argument("--extractor", default="manual",
                      choices=["manual", "spacy", "stanza", "llm", "rule", "import"],
                      help="Source de l'extraction (défaut: manual)")
    p_am.add_argument("--confidence", type=float, default=None,
                      help="Score de confiance 0.0–1.0")

    # ---- search-person ----
    p_sp = sub.add_parser("search-person", help="Recherche une personne par nom ou alias.")
    p_sp.add_argument("--name", required=True, help="Nom ou alias à rechercher")
    p_sp.add_argument("--limit", type=int, default=10)

    # ---- list-mentions ----
    p_lm = sub.add_parser("list-mentions", help="Liste les mentions filtrées.")
    p_lm.add_argument("--person-key", dest="person_key", default=None,
                      help="Filtrer par clé de personne")
    p_lm.add_argument("--source", default=None, help="Filtrer par fichier source")
    p_lm.add_argument("--limit", type=int, default=50)

    # ---- stats ----
    sub.add_parser("stats", help="Statistiques globales sur la base.")

    # ---- list-sources ----
    p_ls = sub.add_parser("list-sources", help="Liste les sources indexées dans SQLite.")
    p_ls.add_argument(
        "--identifiant-technique",
        dest="identifiant_technique",
        default=None,
        help="Filtrer par identifiant technique exact",
    )
    p_ls.add_argument(
        "--url",
        default=None,
        help="Filtrer par URL exacte (avec tolérance sur le slash final)",
    )
    p_ls.add_argument(
        "--origine",
        default=None,
        help="Filtrer par origine (contains)",
    )
    p_ls.add_argument("--limit", type=int, default=50)

    # ---- list-source-documents ----
    p_lsd = sub.add_parser(
        "list-source-documents",
        help="Liste les documents indexés dans source_document.",
    )
    p_lsd.add_argument(
        "--ner-status",
        type=int,
        choices=[0, 1, 2],
        default=None,
        dest="ner_status",
        help="Filtrer par statut NER (0, 1, 2)",
    )
    p_lsd.add_argument(
        "--source",
        default=None,
        help="Filtrer par chemin de document, identifiant_source ou titre",
    )
    p_lsd.add_argument("--limit", type=int, default=50)

    # ---- export-person ----
    p_ep = sub.add_parser("export-person", help="Export JSON d'une personne + ses mentions.")
    p_ep.add_argument("--person-key", required=True, dest="person_key",
                      help="Clé métier de la personne")
    p_ep.add_argument("--out", default=None, help="Fichier JSON de sortie (défaut: stdout)")

    # ---- merge-persons ----
    p_mp = sub.add_parser(
        "merge-persons",
        help="Fusionne deux personnes : transfère les mentions de SOURCE vers TARGET "
             "et ajoute le nom source comme alias. SOURCE est ensuite supprimée.",
    )
    p_mp.add_argument("--source-key", required=True, dest="source_key",
                      help="Clé de la personne à absorber (sera supprimée)")
    p_mp.add_argument("--target-key", required=True, dest="target_key",
                      help="Clé de la personne cible (conservée, enrichie)")

    # ---- reset-ner-analysis ----
    sub.add_parser(
        "reset-ner-analysis",
        help="Supprime toutes les mentions et repasse les source_document de ner_status=2 à ner_status=1.",
    )

    # ---- upsert-source ----
    p_us = sub.add_parser("upsert-source", help="Crée ou met à jour une source (ou un document dérivé).")
    p_us.add_argument("--identifiant-technique", dest="identifiant_technique", default="",
                      help="Identifiant technique stable (MD5 du fichier si omis pour une source originale)")
    p_us.add_argument("--identifiant-source", dest="identifiant_source", required=True,
                      help="Identifiant lisible de la source (ex. 'swissvotes-86')")
    p_us.add_argument("--titre", required=True, help="Titre de la source")
    p_us.add_argument("--origine", required=True,
                      help="Chemin relatif (depuis la racine du dépôt) ou URL du fichier source")
    p_us.add_argument("--date-publication", dest="date_publication", default="0000-00-00",
                      help="Date de publication ISO 8601 (défaut: 0000-00-00)")
    p_us.add_argument("--date-consultation", dest="date_consultation", default="0000-00-00",
                      help="Date de consultation ISO 8601 (défaut: 0000-00-00)")
    p_us.add_argument("--auteurs", nargs="*", default=[],
                      help="Liste des auteurs")
    p_us.add_argument("--periodes", nargs="*", default=[],
                      help="Périodes couvertes (ex. '1939-1945')")
    p_us.add_argument("--isbn", default="", help="ISBN")
    p_us.add_argument("--issn", default="", help="ISSN")
    p_us.add_argument("--doi", default="", help="DOI")
    p_us.add_argument("--url", default="", help="URL canonique de la source")
    p_us.add_argument("--langues", default=None, help="Langue(s) du document (ex. 'fr')")
    p_us.add_argument("--pertinence", type=float, default=0.0,
                      help="Score de pertinence 0.0–1.0 (défaut: 0.0)")
    p_us.add_argument("--type-source", dest="type_source", default="secondaire",
                      choices=["primaire", "secondaire", "tertiaire"],
                      help="Type de source (défaut: secondaire)")
    p_us.add_argument("--lisible", action="store_true", default=False,
                      help="Indique que le document est lisible/indexable")
    p_us.add_argument("--nombre-pages", dest="nombre_pages", type=int, default=-1,
                      help="Nombre de pages (-1 si inconnu)")
    p_us.add_argument("--categorie", default="autre",
                      help="Catégorie du document (défaut: autre)")
    p_us.add_argument("--extrait-brut", dest="extrait_brut", default="",
                      help="Extrait brut du document")
    p_us.add_argument("--resume", default="", help="Résumé du document")
    p_us.add_argument("--parent-path", dest="parent_path", default="",
                      help="Chemin relatif du document parent (pour un document dérivé)")
    p_us.add_argument("--file-name", dest="file_name", default="",
                      help="Nom du fichier (déduit de --origine si omis)")
    p_us.add_argument("--relative-path", dest="relative_path", default="",
                      help="Chemin relatif interne à la source")
    p_us.add_argument("--author", default="", help="Auteur du document dérivé")
    p_us.add_argument("--ner-status", dest="ner_status", type=int, default=None,
                      choices=[0, 1, 2],
                      help="Statut NER du document (0=non traité, 1=à traiter, 2=traité)")

    return parser


COMMANDS = {
    "upsert-person": cmd_upsert_person,
    "add-mention":   cmd_add_mention,
    "search-person": cmd_search_person,
    "list-mentions": cmd_list_mentions,
    "list-sources":  cmd_list_sources,
    "list-source-documents": cmd_list_source_documents,
    "stats":         cmd_stats,
    "export-person": cmd_export_person,
    "merge-persons": cmd_merge_persons,
    "reset-ner-analysis": cmd_reset_ner_analysis,
    "upsert-source": cmd_upsert_source,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()

