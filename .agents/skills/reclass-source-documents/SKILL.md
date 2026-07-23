---
name: reclass-source-documents
description: Reclass source document clusters in a directory into subfolders grouped by publication year from Markdown front matter.
---

# Reclass Source Documents

Ce skill reclasse les grappes de documents d'un repertoire (source originale, Markdown, images liees, artefacts derives) dans des sous-repertoires d'annee.

## Critere supporte

- `publication-year` (par defaut): annee extraite du front matter YAML d'un fichier Markdown de la grappe (`date_publication`, `publication_date`, `date`, `date-publication`).

## Contraintes respectees

- Tous les fichiers d'une meme grappe restent ensemble dans le meme repertoire parent cible (`<repertoire>/<annee>/...`).
- Synchronisation SQLite apres deplacement:
  - table `source` (`origine`),
  - table `source_document` (`path`, `file_name`),
  - table `mention` (`source`).

## Inputs

- `--directory` (obligatoire): repertoire a reclasser (relatif au depot ou absolu).
- `--group-by` (optionnel): `publication-year` uniquement.
- `--dry-run` (optionnel): affiche le plan sans appliquer les changements.
- `--db` (optionnel): chemin vers la base SQLite (defaut: `named_entities.sqlite`).

## Commandes

Simulation:

```powershell
python -u ".agents/skills/reclass-source-documents/scripts/reclass_source_documents.py" --directory "sources/vie_politique/conseil_communal/archives" --dry-run
```

Execution:

```powershell
python -u ".agents/skills/reclass-source-documents/scripts/reclass_source_documents.py" --directory "sources/vie_politique/conseil_communal/archives"
```

