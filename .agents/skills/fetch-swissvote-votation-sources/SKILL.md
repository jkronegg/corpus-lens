---
name: fetch-swissvote-votation-sources
description: Télécharge des documents officiels pour une votation fédérale suisse en fonction du numéro de votation.
---

# Obtention des sources officielles de la votation

Ce skill lance `scripts/swissvote_fetch_votation_sources.py` pour automatiser toute la procédure.

## Inputs

- `--votation-id` (requis): identifiant Swissvotes (ex: `119`, `639`)
- `--output-root` (optionnel): dossier racine de sortie (défaut: `sources/swissvotes`)
- `--timeout` (optionnel): timeout HTTP en secondes (défaut: `45`)
- `--dry-run` (optionnel): affiche les chemins et URL cibles sans telechargement

## Outputs

Le script créé `sources/swissvotes/votation_<votation_id>/` et y écrit:

- `votation_<votation_id>.html` (page Swissvotes brute)
- `votation_<votation_id>.md` (snapshot Markdown de la page)
- `chronologie_officielle.md` (chronologie officielle convertie en Markdown lisible)
- `message_conseil_federal.<ext>` (document officiel)
- `votation_<votation_id>_download_summary.json` (résumé des téléchargements)

Notes:

- Pour les documents HTML officiels (notamment la chronologie), le script tente la variante française via la balise `link rel="alternate" lang="fr"` puis suit la redirection HTTP avant sauvegarde/conversion.

## Commandes

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py" --votation-id 639
```

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py" --votation-id 119 --dry-run
```
