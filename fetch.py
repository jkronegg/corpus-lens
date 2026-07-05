#!/usr/bin/env python3
"""Dispatcher CLI pour les skills fetch-*.

Invoque le script sous-jacent au skill approprié depuis la racine du projet.

Usage:
    python fetch.py <source> <requête> [options supplémentaires...]

Exemples:
    python fetch.py dhs "affaire des colonels"
    python fetch.py dhs affaire des colonels
    python fetch.py wikipedia "affaire des colonels"
    python fetch.py wikipedia affaire des colonels --lang en
    python fetch.py dodis-person "Jean Pascal Delamuraz"
    python fetch.py dodis-person Jean Pascal Delamuraz
    python fetch.py elitesuisse "Thierry Pun"
    python fetch.py enewspaper "affaire des colonels" --start-year 1900 --end-year 1950
    python fetch.py enewspaper-content "https://www.e-newspaperarchives.ch/?a=d&d=..."
    python fetch.py url "https://example.com"
    python fetch.py swissvote 639
    python fetch.py dodis "https://dodis.ch/search?q=panama&c=Document"
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Table des sous-commandes
# ---------------------------------------------------------------------------
# Chaque entrée définit :
#   script        : chemin relatif depuis la racine du projet
#   primary_flag  : flag argparse attendu pour la valeur principale (query/titre/…)
#   help          : description courte
#
# Les alias pointent vers la clé canonique via "alias".
# ---------------------------------------------------------------------------
SUBCOMMANDS: dict[str, dict[str, Any]] = {
    "dhs": {
        "script": ".agents/skills/fetch-dhs-article/scripts/dhs_fetch_article.py",
        "primary_flag": "--term",
        "help": "Télécharge un article DHS (Dictionnaire historique de la Suisse).",
        "usage": "fetch dhs <terme de recherche>",
    },
    "wikipedia": {
        "script": ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py",
        "primary_flag": "--title",
        "help": "Télécharge un article Wikipedia.",
        "usage": "fetch wikipedia <titre>",
    },
    "wiki": {"alias": "wikipedia"},
    "dodis": {
        "script": ".agents/skills/fetch-dodis-results/scripts/dodis_fetch_results.py",
        "primary_flag": "--url",
        "help": "Extrait les résultats d'une recherche Dodis (documents).",
        "usage": "fetch dodis <URL de recherche Dodis>",
    },
    "dodis-person": {
        "script": ".agents/skills/fetch-dodis-person-details/scripts/fetch_dodis_person_details.py",
        "primary_flag": "--name",
        "help": "Exporte la fiche d'une personne depuis l'index Dodis.",
        "usage": "fetch dodis-person <nom complet>",
    },
    "dodis-p": {"alias": "dodis-person"},
    "elitesuisse": {
        "script": ".agents/skills/fetch-elitesuisse-person-details/scripts/fetch_elitesuisse_person_details.py",
        "primary_flag": "--name",
        "help": "Exporte la fiche d'une personne depuis l'index EliteSuisses.",
        "usage": "fetch elitesuisse <nom complet>",
    },
    "elite": {"alias": "elitesuisse"},
    "enewspaper": {
        "script": ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py",
        "primary_flag": "--query",
        "help": "Liste les articles de e-newspaperarchives.ch selon une recherche.",
        "usage": "fetch enewspaper <requête> [--start-year N] [--end-year N]",
    },
    "enpa": {"alias": "enewspaper"},
    "enewspaper-content": {
        "script": ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py",
        "primary_flag": "--article-url",
        "help": "Télécharge le contenu d'un article e-newspaperarchives.ch.",
        "usage": "fetch enewspaper-content <URL article> [--input-json <fichier.json>]",
    },
    "enpa-content": {"alias": "enewspaper-content"},
    "url": {
        "script": ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py",
        "primary_flag": "--url",
        "help": "Télécharge un document depuis une URL générique (PDF, HTML, etc.).",
        "usage": "fetch url <URL>",
    },
    "generic": {"alias": "url"},
    "swissvote": {
        "script": ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py",
        "primary_flag": "--votation-id",
        "help": "Télécharge les sources officielles d'une votation fédérale suisse.",
        "usage": "fetch swissvote <id_votation>",
    },
    "votation": {"alias": "swissvote"}
}


def resolve(name: str) -> dict[str, Any] | None:
    """Résout un nom de sous-commande (alias inclus) vers sa définition."""
    entry = SUBCOMMANDS.get(name)
    if entry is None:
        return None
    if "alias" in entry:
        return SUBCOMMANDS.get(str(entry["alias"]))
    return entry


def canonical_name(name: str) -> str:
    """Retourne le nom canonique d'une sous-commande (suit les alias)."""
    entry = SUBCOMMANDS.get(name, {})
    return str(entry.get("alias", name))


def print_help() -> None:
    print("Usage: fetch <source> <requête> [options supplémentaires...]")
    print()
    print("Sources disponibles:")
    for name, entry in SUBCOMMANDS.items():
        if "alias" in entry:
            continue
        aliases = [k for k, v in SUBCOMMANDS.items() if v.get("alias") == name]
        alias_str = f"  (alias: {', '.join(aliases)})" if aliases else ""
        print(f"  {name}{alias_str}")
        print(f"    {entry['help']}")
        print(f"    {entry['usage']}")
    print()
    print("Exemples:")
    print('  fetch dhs "affaire des colonels"')
    print("  fetch dhs affaire des colonels")
    print('  fetch wikipedia "affaire des colonels"')
    print('  fetch wikipedia affaire des colonels --lang de')
    print('  fetch dodis-person "Jean Pascal Delamuraz"')
    print('  fetch elitesuisse "Thierry Pun"')
    print('  fetch enewspaper "affaire des colonels" --start-year 1900 --end-year 1960')
    print('  fetch enewspaper-content "https://www.e-newspaperarchives.ch/?a=d&d=..."')
    print('  fetch url "https://example.com/document.pdf"')
    print('  fetch swissvote 639')
    print('  fetch dodis "https://dodis.ch/search?q=panama&c=Document"')
    print()
    print("Options génériques (passées directement au script sous-jacent):")
    print("  --dry-run          Vérifie sans télécharger")
    print("  --out-dir <dir>    Dossier de sortie")
    print("  --help             Affiche l'aide du script sous-jacent")


def split_primary_and_extra(args: list[str]) -> tuple[str, list[str]]:
    """Sépare les tokens de valeur primaire (avant tout flag --) des flags passthrough.

    Les mots qui ne commencent pas par '-' et précèdent le premier flag '--xxx'
    constituent la valeur principale (query, titre, nom, etc.).
    Tout ce qui suit (flags '--xxx') est transmis tel quel au script.
    """
    primary_tokens: list[str] = []
    extra_args: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            extra_args.extend(args[i:])
            break
        primary_tokens.append(arg)
        i += 1
    return " ".join(primary_tokens).strip(), extra_args


def build_command(cmd_def: dict[str, Any], primary_value: str, extra_args: list[str]) -> list[str]:
    """Construit la liste d'arguments pour subprocess."""
    script_path = REPO_ROOT / str(cmd_def["script"])
    cmd: list[str] = [sys.executable, "-u", str(script_path)]

    if primary_value:
        cmd.extend([str(cmd_def["primary_flag"]), primary_value])

    cmd.extend(extra_args)
    return cmd


def main() -> int:
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    subcommand = argv[0].lower()
    rest = argv[1:]

    cmd_def = resolve(subcommand)
    if cmd_def is None:
        canonicals = sorted(k for k, v in SUBCOMMANDS.items() if "alias" not in v)
        print(f"[erreur] Sous-commande inconnue: '{subcommand}'", file=sys.stderr)
        print(f"  Sous-commandes disponibles: {', '.join(canonicals)}", file=sys.stderr)
        return 2

    script_path = REPO_ROOT / str(cmd_def["script"])
    if not script_path.exists():
        print(f"[erreur] Script introuvable: {script_path}", file=sys.stderr)
        return 2

    primary_value, extra_args = split_primary_and_extra(rest)

    # Cas particulier : si l'utilisateur passe --help, on transmet sans valeur primaire.
    if not primary_value and not extra_args:
        extra_args = ["--help"]

    cmd = build_command(cmd_def, primary_value, extra_args)

    # Afficher la commande effectivement lancée pour traçabilité.
    display_args = cmd[3:]  # Sauter python, -u et le chemin du script
    display = " ".join(f'"{a}"' if " " in a else a for a in display_args)
    print(f"[fetch:{canonical_name(subcommand)}] {Path(cmd[2]).name} {display}")
    print()

    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())


