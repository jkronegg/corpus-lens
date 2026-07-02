---
name: fetch-enewspaper-article-content
description: Télécharge le contenu d'articles de e-newspaperarchives.ch en Markdown depuis une liste d'articles JSON ou une liste d'URL.
---

# e-newspaper Fetch Article Content

Ce skill lance `scripts/enewspaper_fetch_article-content.py` pour télécharger le contenu des pages article (`?a=d&d=...`) et sauvegarder chaque article en Markdown.

> Important: ce site est protegé par Cloudflare Turnstile.
> Le skill lance un navigateur headful via CDP, avec attente passive en cas de challenge.

## Inputs

- `--input-json`: fichier JSON issu de `enewspaper_fetch_results.py`.
- `--article-url`: URL d'article directe (option répétable).
- `--output-dir`: dossier de sortie (defaut: `sources/enewspaper/articles`).
- `--wait-time`: attente après chargement de page (defaut: `3.5` sec).
- `--pause-on-challenge`: attente passive prolongable si Turnstile détecté.
- `--cdp-url`: endpoint CDP explicite.
- `--max-articles`: limite du nombre d'articles à traiter.
- `--dry-run`: affiche la configuration sans téléchargement.
- `--verbose`: (optionnel) affiche le détail complet (JSON) des articles télécharges; par défaut seule une ligne de résumé est affichée.

## Outputs

Le script écrit:

- Un fichier Markdown par article téléchargé.
- En mode `--verbose` uniquement: un résumé JSON `download_articles_summary_<timestamp>.json`.

## Commandes

```powershell
python -u ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py" --dry-run --article-url "https://www.e-newspaperarchives.ch/?a=d&d=TEST0001"
```

```powershell
python -u ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py" `
  --input-json "sources/enewspaper/enewspaper_votation_1935_YYYYMMDD_HHMMSS.json" `
  --max-articles 10 `
  --pause-on-challenge
```

## Related files

- skill `enewspaper_fetch_article-list` : obtenir une liste d'articles
- `scripts/smoke_test_enewspaper_fetch_article-content.py`

