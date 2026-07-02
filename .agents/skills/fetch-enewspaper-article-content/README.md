# fetch-enewspaper-article-content

Skill dedie au telechargement des pages article de `e-newspaperarchives.ch` en Markdown.

## Prerequis

- Python 3.10+
- `playwright` installe
- Navigateurs Playwright installes (`playwright install chromium`)

## Test rapide

```powershell
python -u ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py" --dry-run --article-url "https://www.e-newspaperarchives.ch/?a=d&d=TEST0001"
```

## Usage principal

Depuis un JSON de resultats genere par le skill `fetch-enewspaper-article-list`:

```powershell
python -u ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py" `
  --input-json "sources/enewspaper/enewspaper_votation_1935_YYYYMMDD_HHMMSS.json" `
  --max-articles 10 `
  --pause-on-challenge
```

Ou avec des URLs directes:

```powershell
python -u ".agents/skills/fetch-enewspaper-article-content/scripts/enewspaper_fetch_article-content.py" `
  --article-url "https://www.e-newspaperarchives.ch/?a=d&d=EXEMPLE1" `
  --article-url "https://www.e-newspaperarchives.ch/?a=d&d=EXEMPLE2"
```

