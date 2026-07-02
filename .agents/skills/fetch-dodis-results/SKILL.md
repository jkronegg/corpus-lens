---
name: fetch-dodis-results
description: Recherche Dodis orientée documents (c=Document) et export des résultats en JSON/Markdown.
capabilities:
  - document-search
  - diplomatic-records-lookup
entity_types:
  - institution
  - country
  - event
  - topic
  - document
search_hints:
  person_queries:
    strategy: delegate
    delegate_to: fetch-dodis-person-details
    also_search:
      - fetch-dhs-article
      - fetch-elitesuisse-person-details
      - fetch-dodis-person-details
  document_queries:
    strategy: prefer-first

---

# Dodis Fetch Results (Documents)

Ce skill lance `scripts/dodis_fetch_results.py` pour exécuter une recherche Dodis de type document (`c=Document`), parcourir la pagination, extraire toutes les colonnes du tableau (`Date`, `N°`, `Type`, `Sujet`, `Résumé`, `Langue`, `URL`) et écrire les résultats en JSON et en Markdown.

Pour les recherches sur des personnes Dodis, utiliser `fetch-dodis-person-details`.

> **⚠️ Important** : N'ouvre pas et ne lis pas le fichier `scripts/dodis_fetch_results.py` par défaut — exécute-le seulement. ⚠️
> Exception : lis ce fichier uniquement si tu dois **modifier le comportement du skill**.

## Inputs

- `--url` **(obligatoire)** : URL de recherche Dodis.
- `--output-dir` : dossier de sortie, par défaut `sources/dodis`.
- `--max-pages` : nombre maximum de pages à traiter, par défaut `20`.
- `--wait-time` : attente après chargement, par défaut `3.5` secondes.
- `--headful` : ouvre le navigateur visible.
- `--pause-on-challenge` : pause manuelle si Dodis affiche un challenge anti-bot.
- `--dry-run` : affiche seulement ce qui serait lancé.

## Outputs

Le script écrit dans `sources/dodis/` par défaut :

- un fichier `dodis_<requête>_<timestamp>.json`
- un fichier `dodis_<requête>_<timestamp>.md`

Le JSON contient les résultats structurés. Le Markdown contient un résumé global et le détail par page. Le script affiche aussi un résumé final sur la sortie standard.

## Commande

```powershell
python -u ".agents/skills/fetch-dodis-results/scripts/dodis_fetch_results.py" `
  --url "https://dodis.ch/search?q=1935&c=Document&f=All&t=all&cb=doc" `
  --headful `
  --pause-on-challenge
```

## Notes

- Utiliser `--headful --pause-on-challenge` si Dodis active sa protection anti-bot.
- Ce skill collecte uniquement les résultats de recherche, pas le contenu détaillé de chaque document.

## Related files
- `scripts/categorisation_de_source/sync_sources_json.py`
