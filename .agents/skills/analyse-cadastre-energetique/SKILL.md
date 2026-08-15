---
name: analyse-cadastre-energetique
description: Interroge la base `regener` du cadastre energetique vaudois avec des questions en langage naturel et produit des resultats tabulaires/Markdown.
---

# Analyse du cadastre energetique vaudois

## Objectif

Ce skill permet d'interroger la table `regener` de la base GeoPackage avec une question en langage naturel.
Le script traduit l'intention vers une requete SQL parametree, execute la requete, puis retourne un tableau lisible.

## Assets

- `assets/Cadastre_energetique_des_batiments_vaudois_103-VD.1.gpkg`
- `assets/MGDM_103VD_EnergetiqueBatiments_V1.1.2.md` (documentation des colonnes et du modele)

## Script

- `scripts/analyse_cadastre_energetique.py`

## Inputs

- `--question` (requis) : question en langage naturel.
- `--output` (optionnel) : ecrit un rapport Markdown.
- `--json` (optionnel) : affiche une sortie JSON.
- `--show-schema` (optionnel) : affiche un extrait de la documentation schema.

## Intentions prises en charge

- Statistiques generales (batiments, communes, CO2 total, besoins chauffage)
- Top communes par CO2 direct
- Repartition par energie de chauffage (`genh1`)
- Analyse des batiments au mazout
- Top communes par nombre de batiments au mazout
- Repartition par epoque energetique
- Liste des batiments d'une commune OFS (`commune 5434`)
- Requete explicite SQL en lecture seule (`sql: SELECT ...`)

## Exemples PowerShell

```powershell
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "statistiques generales"
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "top 10 communes par co2"
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "analyse mazout"
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "liste batiments commune 5434" --output "initiatives/world_model_mazout/rapport_commune_5434.md"
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "sql: SELECT ggdename, COUNT(*) AS nb FROM regener GROUP BY ggdename ORDER BY nb DESC LIMIT 5"
```

## Notes

- Le mode `sql:` accepte uniquement des requetes `SELECT` sans instructions de modification.
- Le jugement historique et l'interpretation finale restent humains; le skill fournit une aide documentaire et quantitative.
- utilise [debug.md](debug.md) s'il y a un problème à l'exécution ou si tu dois modifier le skill.
