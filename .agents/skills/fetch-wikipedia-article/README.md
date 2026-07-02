# fetch-wikipedia-article

Télécharge un article Wikipedia via l'API MediaWiki et l'exporte en Markdown.

## Fichiers

- `SKILL.md`
- `requirements.txt`
- `scripts/fetch_wikipedia_article.py`
- `scripts/test_fetch_wikipedia_article.py`

## Exécution rapide

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels"
```

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels" --dry-run
```

## Test unitaire

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/test_fetch_wikipedia_article.py"
```

## Sortie

Par défaut, le Markdown est écrit dans `sources/wikipedia/` avec un front matter YAML contenant:

- `title`
- `date`
- `author`
- `sources`

