---
name: analyse-consommation-pv-batterie
description: Analyse une courbe de charge quart-horaire et propose un pré-dimensionnement photovoltaïque + batterie pour maximiser l'autoconsommation.
---

# Analyse consommation électrique pour PV+batterie

## Objectif

Ce skill aide à pré-dimensionner un système photovoltaïque (PV) et une batterie domestique
sur la base d'une consommation quart-horaire:

- calcul des statistiques mensuelles par plage horaire,
- distinction semaine vs week-end,
- calcul de la puissance de pointe (kW),
- simulation simplifiée de production PV (profil standard Vaud),
- comparaison de scénarios PV+batterie pour maximiser l'autoconsommation.

## Script

- `scripts/analyse_consommation_pv_batterie.py`

## Entrées

- `--input-csv` (requis): CSV quart-horaire au format `Date;Consommation`.
  - Colonne 1: timestamp `%d.%m.%Y %H:%M:%S`
  - Colonne 2: consommation du quart d'heure en kWh.
- `--output` (optionnel): rapport Markdown de sortie.
- `--json-output` (optionnel): export JSON structuré.
- `--pv-kwp-list` (optionnel): liste de puissances PV testées, ex. `5,10,15`.
  - Mode legacy: utilisé seulement si aucun nombre de panneaux orientés n'est fourni.
- `--battery-kwh-list` (optionnel): liste de batteries testées, ex. `0,5,10,15`.
- `--battery-dod` (optionnel): profondeur de décharge batterie (défaut `0.8`).
- `--battery-roundtrip-efficiency` (optionnel): rendement aller-retour batterie (défaut `0.9`).
- `--panel-watt-peak` (optionnel): puissance nominale d'un panneau standard (défaut `430`).
- `--panels-north` (optionnel): nombre de panneaux installables au nord.
- `--panels-south` (optionnel): nombre de panneaux installables au sud.
- `--panels-east` (optionnel): nombre de panneaux installables à l'est.
- `--panels-west` (optionnel): nombre de panneaux installables à l'ouest.
- `--top-n-scenarios` (optionnel): nombre de scénarios affichés dans le rapport.

## Sorties

- Rapport Markdown avec:
  - qualité des données par mois,
  - plancher/plafond de consommation horaire par mois/plage/type de jour,
  - consommation totale par plage (min, médiane, max) par jour,
  - pic de puissance max (kW),
  - classement des scénarios PV+batterie,
  - recommandation de pré-dimensionnement.
- JSON optionnel avec les métriques détaillées.

## Plages horaires analysées

- `22h-6h`
- `6h-9h`
- `9h-16h`
- `16h-22h`

## Hypothèses de production PV (version standard)

- Profil mensuel simplifié pour le canton de Vaud (kWh/kWp/jour).
- Distribution journalière simplifiée de la production sur les heures 6h-19h.
- Si des panneaux par orientation sont fournis, la production est répartie par orientation:
  - sud: profil de référence,
  - est: profil plus matinal et rendement légèrement réduit,
  - ouest: profil plus tardif et rendement légèrement réduit,
  - nord: rendement réduit.
- Pas de météo réelle, pas d'ombrage ni de masque détaillé.

## Exemple PowerShell

```powershell
python -u ".agents/skills/analyse-consommation-pv-batterie/scripts/analyse_consommation_pv_batterie.py" --input-csv "sources/romande-energie/jk_kronegg_ch/romande_energie_quarter_hourly.csv" --panels-south 24 --panels-east 12 --panels-west 12 --panels-north 0 --battery-kwh-list "5,10,15,20" --output "sortie/analyse_pv_batterie.md" --json-output "sortie/analyse_pv_batterie.json"
```

## Notes méthodologiques

- La colonne consommation est déjà en kWh par quart d'heure.
- La consommation horaire (kWh/h) est calculée par somme des 4 quarts de l'heure.
- La puissance de pointe (kW) est calculée sur le pas quart-horaire: `kW = kWh_quart * 4`.
- Si des panneaux orientés sont fournis, la puissance PV simulée correspond à la somme des panneaux installables par orientation multipliée par `--panel-watt-peak`.
- Le dimensionnement produit est un pré-dimensionnement énergétique, pas un devis technique final.
- Le jugement final reste humain et doit être vérifié avec les sources et contraintes réelles du bâtiment.

