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

## Inputs du script

- `--title` (obligatoire): titre de l'article Wikipedia.
- `--lang`: code langue Wikipedia (défaut: `fr`).

## Outputs du script

Le script affiche en retour un objet JSON:
- Si l'article est trouvé: un fichier Markdown avec front matter YAML dans `sources/wikipedia/`.
- Si l'article n'est pas trouvé: message JSON explicite `found: false`, aucun fichier créé.

## Commandes

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels"
```

## Output du skill

Fais un message de feedback minimal :
- si l'article est trouvé: lien vers le fichier Markdown généré
- si l'article n'est pas trouvé: message d'erreur.

## Notes

- S'il y a un problème d'exécution du script, consulte [debug.md](debug.md)

