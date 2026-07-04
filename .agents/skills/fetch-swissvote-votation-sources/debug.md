## Input supplémentaires pour le mode debug

- `--output-root` (optionnel): dossier racine de sortie (défaut: `sources/swissvotes`)
- `--timeout` (optionnel): timeout HTTP en secondes (défaut: `45`)
- `--dry-run` (optionnel): affiche les chemins et URL cibles sans telechargement

## Commandes supplémentaires pour le mode debug

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py" --votation-id 119 --dry-run
```

Notes:

- Pour les documents HTML officiels (notamment la chronologie), le script tente la variante française via la balise `link rel="alternate" lang="fr"` puis suit la redirection HTTP avant sauvegarde/conversion.
