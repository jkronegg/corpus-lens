# Analyse de la population suisse

## Pyramide des âges des hommes et femmes habitants en Suisse, au cours du temps

Le fichier `assets/ds-x-01.03.01.02.master.json` contient la pyramide des âges des habitants de Suisse au cours du temps. La structure est la suivante:
data contient une Map "year" -> Map sexe ("M"=homme, "F"=femme) -> map âge ("0"=0 ans) -> map projection A/B/C contenant l'effectif.

Les projections A/B/C décrivent trois scénarios d'évolution de la population suisse, basés sur des hypothèses différentes de fécondité, mortalité et migration. Les chiffres A/B/C sont identiques pour les années avant ~2020 et divergents pour les années futures (à partir de 2020 environ).

## Pourcentage d'étrangers dans la population suisse au cours du temps

Le fichier `assets/pourcentage_etrangers_suisse_par_annee.csv` contient une série annuelle du pourcentage d'étrangers dans la population suisse, de 180 à 2015.

Note: Il est obtenu à partir de données officielles de l'Office fédéral de la statistique (OFS): https://mapexplorer.bfs.admin.ch/?obs=historique&lang=fr#c=indicator&i=pop_etrangere.pxx_pop_e_2015&view=map203.

## Pourcentage de la population suisse de nationalité suisse et de 18 ans et plus, au cours du temps

Le fichier `assets/habitants_suisses_18plus_par_annee.csv` contient une série annuelle du nombre d'habitants suisses de 18 ans et plus, de 1910 à 2025. Cette série est utilisée pour normaliser le nombre de signatures valides déposées pour les initiatives populaires fédérales, afin d'obtenir un ratio représentatif du vivier potentiel de signataires.
Il est produit par le script `scripts/export_habitants_suisses_18plus_par_annee.py`.