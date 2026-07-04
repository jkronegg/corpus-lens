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
  - Debates of the National Council and Council of States
  - Official results
  - Le script créé `sources/swissvotes/votation_<votation_id>/` et y écrit:
- Writes a JSON summary file

For HTML official pages, the script tries to switch to French by using the page alternate link (`rel="alternate"`, `lang="fr"`) and follows the HTTP redirection before saving/conversion.

La liste des votations est dans [DATASET CSV 08-04-2026.csv](../analyse-swissvotes-votations/assets/DATASET%20CSV%2008-04-2026.csv)

## Coût

Coût d'un appel avec `/skill:fetch-swissvote-votation-sources`: 1.5 AI credits.