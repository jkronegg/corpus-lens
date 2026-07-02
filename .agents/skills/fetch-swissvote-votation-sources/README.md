# fetch-swissvote-votation-sources

Automates Swissvotes source retrieval for one votation id.

## What it does

- Creates `sources/swissvotes/votation_<id>`
- Downloads `https://swissvotes.ch/vote/<id>.00` as HTML
- Generates `votation_<id>.md` from extracted page text and links
- Downloads:
  - official chronology source file (`chronologie_officielle.<ext>`)
  - official chronology as Markdown (`chronologie_officielle.md`)
  - Federal Council message
- Writes a JSON summary file

For HTML official pages, the script tries to switch to French by using the page alternate link (`rel="alternate"`, `lang="fr"`) and follows the HTTP redirection before saving/conversion.

## Run

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py" --votation-id 639
```

## Smoke test

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/smoke_test_swissvote_fetch_votation_sources.py"
```

