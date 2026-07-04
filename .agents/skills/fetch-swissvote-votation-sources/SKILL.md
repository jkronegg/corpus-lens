---
name: fetch-swissvote-votation-sources
description: Télécharge des documents officiels pour une votation fédérale suisse en fonction du numéro de votation.
---

## Inputs du script

- `--votation-id` (requis): identifiant Swissvotes (ex: `119`, `639`)

## Outputs du script

Le script retourne un objet JSON indiquant les documents téléchargés.

## Commandes

```powershell
python -u ".agents/skills/fetch-swissvote-votation-sources/scripts/swissvote_fetch_votation_sources.py" --votation-id 639
```

## Output du skill

Fais un message de feedback minimaliste à l'utilisateur:
- indication du répertoire où les fichiers ont été téléchargés
- S'il y a une erreur, message d'erreur explicitant la cause.

## Notes

En cas d'erreur d'exécution du script, consulte [debug.md](debug.md).
Pour davantage d'informations sur le contenu des fichiers, consulte [README.md](README.md)