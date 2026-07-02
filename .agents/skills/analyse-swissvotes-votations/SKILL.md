---
name: analyse-swissvotes-votations
description: Analyse et compare les métadonnées de votations fédérales suisses (chronologie, durées, résultats) à partir du jeu de données Swissvotes.
---

# Analyse des métadonnées de votations Swissvotes

## Objectif

Ce skill extrait et compare les métadonnées structurées d'une ou plusieurs votations fédérales suisses
à partir du jeu de données Swissvotes (CSV officiel). Il permet notamment de :

- consulter la fiche détaillée d'une votation (dates clés, durées, résultats, positions des acteurs)
- comparer deux votations ou plus sur des indicateurs chronologiques (ex. durée entre la fin de la
  récolte des signatures et la votation, durée de traitement parlementaire, etc.)
- produire un tableau comparatif lisible en Markdown et un fichier JSON structuré

## Assets

- **CSV** : `.agents/skills/analyse-swissvotes-votations/assets/DATASET CSV 08-04-2026.csv`
  (séparateur `;`, encodage UTF-8 BOM, 874 colonnes, une ligne par votation)
- **CODEBOOK** : `.agents/skills/analyse-swissvotes-votations/assets/CODEBOOK.md`
  (description complète de chaque colonne, en allemand)

## Colonnes clés utilisées

| Colonne CSV       | Signification                                                                 |
|-------------------|-------------------------------------------------------------------------------|
| `anr`             | Numéro officiel de la votation (Bundesamt für Statistik)                      |
| `datum`           | Date du scrutin                                                               |
| `titel_kurz_f`    | Titre court en français                                                       |
| `titel_off_f`     | Titre officiel en français                                                    |
| `rechtsform`      | Type : 1=réf. obligatoire, 2=réf. facultatif, 3=initiative, 4=contre-projet, 5=question subsidiaire |
| `dat-preexam`     | Date de la pré-examen de l'initiative (si applicable)                         |
| `dat-start`       | Début de la récolte des signatures                                            |
| `dat-limit`       | Fin légale de la récolte (délai légal)                                        |
| `dat-submit`      | Date du dépôt des signatures                                                  |
| `dat-success`     | Date de la constatation officielle du succès (décision du CF)                 |
| `dat-message`     | Date du message du Conseil fédéral au Parlement                               |
| `dat-parl`        | Date de la décision du Parlement                                              |
| `dat-force`       | Date d'entrée en vigueur (0 si rejeté)                                        |
| `sammelfrist`     | Durée légale de la récolte (jours ; 0=pas de récolte, 9999=illimitée)         |
| `dauer_bv`        | Durée de traitement parlementaire (jours, botschaft → parlement)              |
| `dauer_abst`      | Durée entre la décision du parlement et la votation (jours)                   |
| `i-dauer_tot`     | Durée totale (dépôt → votation) pour les initiatives (jours)                  |
| `i-dauer_samm`    | Durée effective de récolte pour les initiatives (jours)                       |
| `i-dauer_br`      | Durée (dépôt → message CF) pour les initiatives (jours)                       |
| `fr-dauer_samm`   | Durée effective de récolte pour les référendums facultatifs (jours)           |
| `fr-dauer_tot`    | Durée totale (botschaft → votation) pour les référendums facultatifs (jours)  |
| `sparedays`       | Jours restants à la récolte lors du dépôt                                     |
| `unter_g`         | Nombre de signatures valides déposées                                         |
| `unter-quorum`    | Quorum de signatures requis                                                   |
| `urheber-fr`      | Auteurs / comité d'initiative (français)                                      |
| `br-pos`          | Position du Conseil fédéral (1=oui, 2=non, 3=sans position)                  |
| `bv-pos`          | Position du Parlement (1=oui, 2=non, 3=sans position, 8=préfère contre-projet)|
| `nr-pos`          | Position du Conseil national                                                  |
| `sr-pos`          | Position du Conseil des États                                                 |
| `volkja-proz`     | % de voix favorables (voix du peuple)                                         |

## Champs complémentaires décrits dans le CODEBOOK

Le `CODEBOOK.md` documente un volume de colonnes bien plus large que la liste minimale ci-dessus.
Si une analyse a besoin d'aller au-delà des dates clés et des résultats synthétiques, se référer explicitement
au codebook et privilégier les familles de champs suivantes.

### 1. Informations générales (`Allgemeines`)

- `titel_kurz_d`, `titel_kurz_e` : titres courts en allemand et en anglais.
- `titel_off_d` : titre officiel en allemand.
- `stichwort` : mot-clé / désignation courte usuelle.
- `swissvoteslink` : lien direct vers la fiche Swissvotes.
- `anzahl` : nombre de votations tenues le même jour.

### 2. Traitement par le Conseil fédéral et le Parlement

- `init_formul` : forme juridique de l'initiative (p. ex. projet rédigé / suggestion générale).
- `kurzbetitel` : titre de la description courte Swissvotes.
- `anneepolitique` : lien vers l'analyse Année Politique Suisse.
- `bkchrono-de`, `bkchrono-fr` : liens vers la chronologie officielle de la Chancellerie.
- `dep` : département fédéral responsable.
- `legislatur`, `legisjahr` : législature et période de législature.
- `gesch_nr` : numéro du dossier parlementaire.
- `entwurf_nr` : numéro de version du projet.
- `curiavista-de`, `curiavista-fr` : liens Curia Vista.
- `pa-iv` : indique l'origine en initiative parlementaire.
- `nrja`, `nrnein`, `srja`, `srnein` : décomptes de votes au Conseil national / Conseil des États.

### 3. Récolte et dépôt des signatures

- `unter_u` : nombre de signatures invalides.
- `sammeltempo` : vitesse de récolte (signatures par jour), pré-calculée dans le dataset.

### 4. Campagne politique (`Abstimmungskampf`)

Cette section est très riche dans le codebook et couvre notamment :

- les ressources officielles d'information :
  - `info_br-de`, `info_br-fr`, `info_br-en`
  - `info_dep-de`, `info_dep-fr`, `info_dep-en`
  - `info_amt-de`, `info_amt-fr`, `info_amt-en`
- les vidéos et sites de campagne :
  - `easyvideo_de`, `easyvideo_fr`
  - `web-yes-1-de` à `web-yes-3-fr`
  - `web-no-1-de` à `web-no-3-fr`
- les mots d'ordre des partis et organisations :
  - `p-fdp`, `p-sps`, `p-svp`, `p-mitte`, `p-gps`, etc.
  - `p-eco`, `p-sgv`, `p-sbv`, `p-sgb`, etc.
  - `p-others_yes`, `p-others_no`, `p-others_free`, `p-others_counterp`, `p-others_init` (+ variantes `-fr`)
- les divergences internes et régionales :
  - variables `pdev-*` pour sections cantonales, ailes jeunesse ou positions divergentes.
- les rapports de force électoraux à la dernière élection fédérale :
  - `nr-wahl`, `w-fdp`, `w-sps`, `w-svp`, etc.
  - agrégats comme `ja-lager`, `nein-lager`, `freigabe-summe`, `neutral-summe`.
- les indicateurs de campagne médiatique et publicitaire :
  - `inserate-total`, `inserate-ja`, `inserate-nein`, `inserate-neutral`, `inserate-jaanteil`
  - `mediares-tot`, `mediares-d`, `mediares-f`
  - `mediaton-tot`, `mediaton-d`, `mediaton-f`
- les informations de financement et de matériel de campagne :
  - `finanz-link-de`, `finanz-link-fr`
  - `finanz-ja-tot`, `finanz-nein-tot`
  - `finanz-ja-gr-de`, `finanz-ja-gr-fr`, `finanz-nein-gr-de`, `finanz-nein-gr-fr`
  - `poster_ja_mfg`, `poster_nein_mfg`, `poster_ja_sa`, `poster_nein_sa`, `poster_ja_bs`, `poster_nein_bs`

### 5. Résultats détaillés du scrutin (`Abstimmungsergebnis`)

- verdicts globaux : `volk`, `stand`, `annahme`.
- participation et validité : `berecht`, `stimmen`, `bet`, `leer`, `ungültig`, `gültig`, `volkja`, `volknein`.
- agrégats cantonaux : `kt-ja`, `kt-nein`, `ktjaproz`.
- résultats par canton : pour chaque canton, familles du type
  - `[canton]-berecht`, `[canton]-stimmen`, `[canton]-bet`, `[canton]-gültig`,
    `[canton]-ja`, `[canton]-nein`, `[canton]-japroz`, `[canton]-annahme`.
- liens de consultation des résultats :
  - `bkresults-de`, `bkresults-fr`
  - `bfsdash-de`, `bfsdash-fr`, `bfsdash-en`
  - `bfsmap-de`, `bfsmap-fr`, `bfsmap-en`

### 6. Post-enquêtes (`Nachbefragung`)

- `nach_cockpit_d`, `nach_cockpit_f`, `nach_cockpit_e` : liens vers les analyses interactives post-votation.

### 7. Ressources documentaires associées

Le codebook mentionne aussi des familles de ressources liées à la fiche d'une votation :

- texte soumis au vote,
- préexamen et dossier d'initiative,
- message du Conseil fédéral,
- débats parlementaires,
- brochure officielle,
- brochure easyvote,
- analyses Année Politique Suisse,
- résultats détaillés BFS,
- rapports post-votation et documents de campagne.

Quand une analyse s'appuie sur ces ressources, le livrable doit expliciter quelle colonne ou quel lien Swissvotes
a été utilisé, et ne pas supposer qu'une ressource est disponible pour toutes les périodes.

## Inputs

- `--votation-ids` (requis) : un ou plusieurs numéros de votation séparés par des virgules (ex. `86,119`)
- `--output` (optionnel) : chemin du fichier de sortie Markdown (défaut : `sortie/comparaison_votations_<ids>.md`)
- `--csv` (optionnel) : chemin du CSV Swissvotes
  (défaut : `.agents/skills/analyse-swissvotes-votations/assets/DATASET CSV 08-04-2026.csv`)
- `--json` (optionnel) : produit aussi un fichier JSON (même chemin, extension `.json`)
- `--bins` (optionnel, histogramme) : nombre d'intervalles pour l'histogramme (défaut `10`)
- `--permutations` (optionnel, analyse opposition) : nombre de permutations pour le test de différence de médiane (défaut `20000`)
- `--votation-id` (optionnel, vitesse initiative) : numéro d'une initiative pour calculer sa vitesse de récolte de signatures

## Outputs

### Fiche unique (une seule votation)

Un fichier Markdown `sortie/comparaison_votations_<id>.md` avec :

- front matter YAML : `title`, `date`, `author`, `votation_ids`
- **Section `## Fiche de la votation`** : tableau de toutes les métadonnées clés
- **Section `## Chronologie`** : liste ordonnée des dates clés avec le nombre de jours entre chaque étape
- **Section `## Résultat`** : résultat du scrutin et positions des acteurs
- **Section `## Incertitudes et données manquantes`** : liste des champs absents ou codés `0`/`.`

### Comparaison (plusieurs votations)

Un fichier Markdown `sortie/comparaison_votations_<ids>.md` avec :

- front matter YAML
- **Section `## Tableau comparatif`** : tableau croisé des indicateurs clés (une ligne par votation)
- **Section `## Analyse des écarts`** : commentaire sur les indicateurs les plus contrastés
  (ex. durée de récolte, durée parlement, résultat)
- **Section `## Incertitudes et données manquantes`**

Et, si `--json` est activé, un fichier JSON avec la même structure mais en données brutes.

### Histogramme dépôt → votation (initiatives)

Un fichier Markdown `sortie/histogramme_duree_depot_votation_initiatives.md` avec :

- front matter YAML
- **Section `## Statistiques descriptives`** : N, min, max, moyenne, médiane, écart-type
- **Section `## Histogramme (<bins> intervalles)`** : histogramme textuel
- **Section `## Tableau des intervalles`** : bornes et fréquences en %
- **Section `## Observations`** : interprétation synthétique

### Histogramme vitesse de récolte des signatures (initiatives)

Un fichier Markdown `sources/swissvotes/histogramme_vitesse_recolte_signatures_initiatives.md` avec :

- front matter YAML
- **Section `## Statistiques descriptives`** : N, min, max, moyenne, médiane, écart-type (signatures/jour)
- **Section `## Histogramme (<bins> intervalles)`** : histogramme textuel de la vitesse
- **Section `## Tableau des intervalles`** : bornes et fréquences en %
- **Section `## Notes méthodologiques`** : règles de calcul/exclusion

### Analyse opposition des autorités → durée (initiatives)

Un fichier Markdown `sortie/analyse_duree_opposition_initiatives.md` avec :

- front matter YAML
- **Section `## Statistiques descriptives par groupe`** : comparaison des durées selon `br-pos` et `bv-pos`
- **Section `## Tests d'hypothèse et taille d'effet`** : test de permutation, Mann-Whitney, Cliff's delta
- **Section `## Contrôle temporel`** : stratification par décennie
- **Section `## Robustesse et équilibre des groupes`** : rappel des effectifs et limites
- **Section `## Conclusion`** et **`## Limites`**

### Vitesse de récolte pour une initiative donnée

Un fichier Markdown `sources/swissvotes/votation_<id>/vitesse_recolte_initiative.md` avec :

- front matter YAML
- **Section `## Résultat`** : dates (`dat-start`, `dat-submit`), durée, signatures valides, vitesse moyenne (signatures/jour)
- **Section `## Position relative parmi les initiatives`** : médiane globale et percentile approximatif
- **Section `## Notes méthodologiques`** : formule de calcul et règles de filtrage

## Commandes

```powershell
# Fiche d'une seule votation
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_votations.py" --votation-ids 86

# Comparaison de deux votations
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_votations.py" --votation-ids 86,119

# Comparaison avec sortie JSON
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_votations.py" --votation-ids 86,119,639 --json

# Fichier de sortie personnalisé
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_votations.py" --votation-ids 86,119 --output sortie/ma_comparaison.md

# Histogramme dépôt -> votation (initiatives), 10 bins
python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_duree_depot_votation.py" --bins 10

# Histogramme avec sortie personnalisée
python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_duree_depot_votation.py" --bins 10 --output sortie/histogramme_custom.md

# Histogramme vitesse de récolte des signatures (initiatives), 10 bins
python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_vitesse_recolte_initiatives.py" --bins 10

# Histogramme vitesse avec sortie personnalisée
python -u ".agents/skills/analyse-swissvotes-votations/scripts/histogramme_vitesse_recolte_initiatives.py" --bins 12 --output sortie/histogramme_vitesse_custom.md

# Analyse durée selon opposition des autorités
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_duree_opposition.py"

# Même analyse avec plus de permutations
python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_duree_opposition.py" --permutations 50000

# Vitesse de récolte pour une initiative
python -u ".agents/skills/analyse-swissvotes-votations/scripts/vitesse_recolte_initiative.py" --votation-id 86

# Vitesse avec sortie personnalisée
python -u ".agents/skills/analyse-swissvotes-votations/scripts/vitesse_recolte_initiative.py" --votation-id 86 --output sortie/vitesse_86.md
```

## Processus

1. Lire le CSV Swissvotes et localiser les lignes correspondant aux `votation-ids` demandés.
2. Extraire les métadonnées clés (dates, durées, résultats, positions).
3. Calculer les durées intermédiaires manquantes si les dates brutes sont disponibles
   (ex. `dat-limit → datum` = durée entre fin de récolte et jour du vote).
4. Pour une fiche unique : produire le fichier Markdown avec toutes les sections décrites ci-dessus.
5. Pour une comparaison : produire le tableau croisé et l'analyse des écarts.
6. Signaler explicitement toute valeur absente (`.`), non applicable (`0`) ou illimitée (`9999`).
7. Écrire le livrable sur disque dans `sortie/` (ne pas se contenter d'une réponse dans le chat).
8. Pour l'histogramme dépôt → votation : filtrer `rechtsform = 3`, calculer `datum - dat-submit` en jours, puis répartir les valeurs selon `--bins`.
9. Pour l'analyse opposition → durée : comparer les groupes `br-pos` / `bv-pos` (`1` vs `2`), calculer les tests et expliciter les limites d'effectif.
10. Pour l'histogramme de vitesse de récolte : filtrer `rechtsform = 3`, calculer `unter_g / (dat-submit - dat-start)` (signatures/jour), exclure les durées non positives et répartir selon `--bins`.
11. Pour la vitesse d'une initiative précise : calculer `unter_g / (dat-submit - dat-start)` pour `--votation-id`, puis comparer au corpus des initiatives valides (médiane + percentile).

## Notes méthodologiques

- Les valeurs `0` dans les colonnes de dates signifient « pas de récolte » (référendums obligatoires).
- Les valeurs `9999` dans `sammelfrist` / `dat-limit` signifient « aucune limite » (initiatives lancées
  avant le 1.7.1978).
- Les valeurs `.` (point seul) signifient « données manquantes ».
- Pour les initiatives touchées par le gel Covid (n° 665, 666, 671), `i-dauer_tot` exclut les 72 jours
  de suspension : mentionner cet ajustement dans la section « Incertitudes ».
- Toutes les durées précalculées par Swissvotes (`dauer_bv`, `dauer_abst`, `i-dauer_*`, `fr-dauer_*`)
  sont en jours ; les convertir en mois (÷ 30,44) pour la lisibilité si la valeur dépasse 90 jours.
- **Limite majeure pour l'analyse opposition → durée** : la proportion d'initiatives où les autorités sont favorables est très faible (ordre de grandeur ~2% du corpus des initiatives valides, p.ex. environ 3/242 pour le CF et 5/242 pour le Parlement dans l'extraction actuelle). Le skill doit toujours signaler explicitement cette asymétrie et éviter toute conclusion causale forte.
- Toutes les phrases rédigées en français dans le Markdown doivent être orthographiées correctement,
  avec les accents et caractères typographiques français (ex. `é`, `à`, `ç`, `œ`). Ne jamais
  translittérer le français en ASCII simple.

