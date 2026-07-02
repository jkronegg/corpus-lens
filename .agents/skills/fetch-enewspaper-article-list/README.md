# fetch-enewspaper-article-list

Skill pour collecter la liste des resultats de recherche de `e-newspaperarchives.ch` avec Playwright.
Le telechargement du texte des articles est gere par le skill `fetch-enewspaper-article-content`.

## Prerequis

- Python 3.10+
- `playwright` installe
- Navigateurs Playwright installes (`playwright install chromium`)

## Test rapide

```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" --dry-run
```

## Execution recommandee (Turnstile)

```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" `
  --query "votation 1935" `
  --start-year 1935 `
  --start-month 1 `
  --pause-on-challenge
```

Le navigateur est **headful par defaut**.
Le script applique aussi une attente initiale plus longue sur la premiere page pour laisser Turnstile se valider.

## Date de debut

- Aucun des trois champs (`--start-day`, `--start-month`, `--start-year`) => pas de date de debut.
- `--start-year` seul => date de debut forcee au 1er janvier.
- `--start-year` + `--start-month` => date de debut forcee au 1er du mois.
- `--start-day` exige `--start-month` et `--start-year`.

## Date de fin

- Aucun des trois champs (`--end-day`, `--end-month`, `--end-year`) => pas de date de fin.
- `--end-year` seul => date de fin forcee au 1er janvier.
- `--end-year` + `--end-month` => date de fin forcee au 1er du mois.
- `--end-day` exige `--end-month` et `--end-year`.
- Si debut et fin sont fournis, la date de fin doit etre >= date de debut.

