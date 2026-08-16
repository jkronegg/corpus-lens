# fetch-romande-energie-data

Skill de téléchargement des courbes de consommation Romande Energie avec authentification user + password + OTP SMS.

## Pré-requis

Ajouter dans le fichier `.env` à la racine du projet:

```dotenv
ROMANDE_ENERGIE_USERNAME=...
ROMANDE_ENERGIE_PASSWORD=...
```

## Utilisation directe

```powershell
python -u ".agents/skills/fetch-romande-energie-data/scripts/fetch_romande_energie_data.py" --granularity QUARTER_HOURLY
```

## Utilisation via le dispatcher

```powershell
python fetch.py romande-energie 2024-12-15 --granularity QUARTER_HOURLY
```

## Cache

Les chunks téléchargés sont conservés sous `.cache/romande-energie/<user_slug>/`.
Chaque chunk couvre une fenêtre de dates sans recouvrement avec les autres chunks.
Le CSV final est reconstruit à chaque exécution à partir du cache.

