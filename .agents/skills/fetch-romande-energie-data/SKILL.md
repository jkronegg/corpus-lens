---
name: fetch-romande-energie-data
description: Télécharge les données de consommation électrique Romande Energie via authentification user + password + OTP SMS, avec cache local par utilisateur.
capabilities:
  - api-download
  - authenticated-fetch
  - csv-merge
  - local-cache
entity_types:
  - dataset
  - timeseries
  - document
---

# Romande Energie Fetch Data

Ce skill télécharge les courbes de consommation électrique depuis l'espace client Romande Energie.

## Consigne d'exécution

- Exécuter directement le script du skill.
- Ne pas décortiquer ni analyser le code du script pour une exécution standard.
- Lire le script uniquement en cas de debug ou d'ajout de fonctionnalités.

## Entrées

- `--start-date` (optionnel): date de début au format `YYYY-MM-DD`.
- `--end-date` (optionnel): date de fin au format `YYYY-MM-DD`.
- `--granularity` (optionnel): `HOURLY`, `QUARTER_HOURLY`, `DAILY`, `MONTHLY`.
- `--out-dir` (optionnel): dossier de sortie des CSV fusionnés.
- `--cache-dir` (optionnel): racine du cache local.

## Sorties

- Un cache local par utilisateur dans `.cache/romande-energie/<user_slug>/`.
- Un CSV fusionné dans `sources/romande-energie/<user_slug>/romande_energie_<granularity>.csv`.
- Les données déjà récupérées sont réutilisées automatiquement via le cache.

## Exemple

```powershell
python -u ".agents/skills/fetch-romande-energie-data/scripts/fetch_romande_energie_data.py" --granularity QUARTER_HOURLY
```

Si `fetch.py` est utilisé, la date de début peut aussi être passée comme valeur primaire:

```powershell
python fetch.py romande-energie 2024-12-15 --granularity QUARTER_HOURLY
```

## Notes

- Si `--start-date` n'est pas fourni, le script choisit automatiquement une date de début.
- Le cache est organisé par utilisateur pour accélérer les exécutions suivantes.

