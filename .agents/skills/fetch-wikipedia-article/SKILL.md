---
name: fetch-wikipedia-article
description: Télécharge un article Wikipedia et l'exporte en Markdown.
capabilities:
  - article-download
  - encyclopedia-lookup
  - reference-lookup
entity_types:
  - article
  - event
  - person
  - concept
  - place
search_hints:
  person_queries:
    strategy: delegate
    delegate_to:
      - fetch-dodis-person-details
      - fetch-elitesuisse-person-details
      - fetch-dhs-article
  document_queries:
    strategy: delegate
    delegate_to: fetch-dodis-results
---

# Wikipedia Fetch Article

Ce skill télécharge le contenu d'un article Wikipedia et l'enregistre en Markdown dans `sources/wikipedia/`.

## Inputs

- `--title` (obligatoire): titre de l'article Wikipedia.
- `--lang`: code langue Wikipedia (défaut: `fr`).
- `--out-dir`: dossier de sortie Markdown (défaut: `sources/wikipedia`).
- `--dry-run`: vérifie la résolution de l'article sans écrire de fichier.

## Outputs

- Si l'article est trouvé: un fichier Markdown avec front matter YAML dans `sources/wikipedia/`.
- Si l'article n'est pas trouvé: message JSON explicite `found: false`, aucun fichier créé.

## Commandes

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels"
```

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels" --dry-run
```

## Notes

- Le skill utilise l'API MediaWiki officielle de Wikipedia.
- Le Markdown généré conserve une structure de sections autant que possible.
- `--dry-run` est réservé au debug.

