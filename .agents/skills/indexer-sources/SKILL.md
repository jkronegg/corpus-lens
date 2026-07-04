---
name: indexer-sources
description: Synchronize sources metadata into the `source` table of `named_entities.sqlite`.
---

# Sync Sources SQLite

Ce skill lance le script de synchronisation des sources et met à jour la table `source` de `named_entities.sqlite`.

## Inputs

- Aucun argument obligatoire.

## Outputs

- Met à jour la table `source` de `named_entities.sqlite`.
- Affiche un resume en sortie standard (`ok: ... sources synchronisees` ou erreurs bloquantes).

## Commande

```powershell
python -u ".agents/skills/indexer-sources/scripts/sync_sources_json.py"
```

## Notes

- Le traitement cible le repertoire `sources/` du projet.
- Règle d'exécution permanente : pour synchroniser les sources, lancer directement la commande du skill sans lire `scripts/sync_sources_json.py` au préalable.
- Exception : lire `scripts/sync_sources_json.py` uniquement lorsqu'une modification du comportement de la synchronisation est demandee.
- Selon le nombre de PDF dont il faut extraire le texte et traduire, le traitement peut être très long: laisse-le se terminer.
