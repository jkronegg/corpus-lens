---
name: analyse-resultats-votation
description: Analyse les résultats d'une votation fédérale suisse par canton et par district à partir du fichier resultats_par_domaine.xlsx fourni par le Bureau fédéral de la statistique.
---

# Analyse des résultats d'une votation par domaine géographique

## Objectif

Ce skill lit le fichier `resultats_par_domaine.xlsx` (BFS) pour une votation fédérale donnée et produit :

- un tableau des résultats nationaux (participation, oui/non, résultat)
- un tableau des résultats par canton, trié par % de oui décroissant
- un tableau des résultats par district (arrondissement de communes), trié par % de oui décroissant
- une analyse géographique (cantons et districts majoritairement favorables vs opposés, diversité régionale, observations sur la carte du vote)

## Structure du fichier source

Le fichier `resultats_par_domaine.xlsx` est fourni par le Bureau fédéral de la statistique (BFS) et contient trois feuilles :

| Feuille     | Contenu                                                                              |
|-------------|--------------------------------------------------------------------------------------|
| `Kantone`   | Résultats agrégés pour les 26 cantons (ou demi-cantons historiques)                  |
| `Bezirke`   | Résultats par district (arrondissement de communes) pour les cantons concernés       |
| `Gemeinden` | Lien vers une source externe pour les données communales (non analysé par ce skill)  |

### Colonnes extraites (Kantone)

| Colonne (position) | Signification                        |
|--------------------|--------------------------------------|
| A                  | Numéro du canton (1–26) ou None      |
| B                  | Nom du domaine (canton, total…)       |
| C                  | Électeurs inscrits (Stimmberechtigte) |
| D                  | Bulletins déposés (Abgegebene Stimmen)|
| E                  | Participation en %                    |
| F                  | Bulletins blancs (leer)               |
| G                  | Bulletins invalides (ungültig)        |
| H                  | Suffrages valables (Gültige Stimmen)  |
| I                  | Voix OUI (JA)                         |
| J                  | Voix NON (NEIN)                       |
| K                  | % OUI (JA in %)                       |

### Colonnes extraites (Bezirke)

Même colonnes A→K, mais A = nom du district (chaîne), pas de numéro.

## Inputs

- `--xlsx` (requis) : chemin vers le fichier `resultats_par_domaine.xlsx`
- `--votation-id` (optionnel) : numéro de la votation (utilisé uniquement pour le nom du fichier de sortie ; si absent, déduit de la cellule A1 du fichier)
- `--output` (optionnel) : chemin du fichier de sortie Markdown
  (défaut : `sources/swissvotes/votation_<id>/resultats_par_domaine.md` si `--votation-id` est fourni,
  sinon `sortie/resultats_par_domaine.md`)
- `--json` (optionnel) : produit aussi un fichier JSON (même chemin, extension `.json`)

## Outputs

### Fichier Markdown

Un fichier Markdown avec un front matter YAML comprenant :
- `title` : « Résultats de la votation n° <id> — <titre> »
- `date` : date de génération
- `author` : « skill analyse-resultats-votation »
- `sources` : chemin du fichier xlsx analysé

Suivi des sections :

- **`## Résultats nationaux`** : tableau avec électeurs inscrits, bulletins déposés, participation %, bulletins blancs, bulletins invalides, suffrages valables, voix OUI, voix NON, % OUI, résultat (accepté / rejeté)
- **`## Résultats par canton`** : tableau trié par % OUI décroissant ; une colonne « Résultat » indique si le canton a voté OUI (`✓`) ou NON (`✗`)
- **`## Majorité cantonale`** : (présente uniquement pour les initiatives et référendums obligatoires) compte du nombre de cantons (et demi-cantons) ayant voté OUI vs NON et indication du résultat de la double majorité requise
- **`## Résultats par district`** : tableau trié par % OUI décroissant ; une colonne « Canton » reconstitue l'appartenance cantonale (sur la base de l'ordre dans le fichier source)
- **`## Analyse géographique`** : commentaire textuel sur :
  - les régions/cantons les plus favorables et les plus opposés
  - les éventuels clivages linguistiques (Röstigraben), urbains/ruraux, confessionnels ou régionaux visibles dans les données
  - les districts qui s'écartent le plus de la tendance de leur canton
- **`## Incertitudes et données manquantes`** : cellules vides, districts sans données de participation, etc.

### Fichier JSON (si `--json`)

```json
{
  "generated": "YYYY-MM-DD",
  "author": "skill analyse-resultats-votation",
  "votation_id": "86",
  "titre": "...",
  "date_scrutin": "...",
  "national": { "inscrits": 0, "bulletins": 0, "participation_pct": 0.0, "blancs": 0, "invalides": 0, "valables": 0, "oui": 0, "non": 0, "oui_pct": 0.0, "resultat": "rejeté" },
  "cantons": [
    { "numero": 1, "nom": "Zurich", "inscrits": 0, "bulletins": 0, "participation_pct": 0.0, "blancs": 0, "invalides": 0, "valables": 0, "oui": 0, "non": 0, "oui_pct": 0.0, "vote": "NON" }
  ],
  "districts": [
    { "nom": "Affoltern", "canton_num": 1, "inscrits": 0, "valables": 0, "oui": 0, "non": 0, "oui_pct": 0.0, "vote": "OUI" }
  ]
}
```

## Commandes

```powershell
# Analyse simple (votation 86)
python -u ".agents/skills/analyse-resultats-votation/scripts/analyse_resultats_votation.py" --xlsx "sources/swissvotes/votation_86/resultats_par_domaine.xlsx" --votation-id 86

# Avec sortie JSON
python -u ".agents/skills/analyse-resultats-votation/scripts/analyse_resultats_votation.py" --xlsx "sources/swissvotes/votation_86/resultats_par_domaine.xlsx" --votation-id 86 --json

# Chemin de sortie personnalisé
python -u ".agents/skills/analyse-resultats-votation/scripts/analyse_resultats_votation.py" --xlsx "sources/swissvotes/votation_86/resultats_par_domaine.xlsx" --votation-id 86 --output "sortie/resultats_votation_86.md"
```

## Processus

1. Ouvrir le fichier xlsx avec `openpyxl` (mode `read_only=True`, `data_only=True`).
2. **Feuille Kantone** :
   a. Lire la ligne 1 (cellule B1) pour la date du scrutin et la ligne 2 (cellule B2) pour le titre de la votation.
   b. Lire le numéro de votation en cellule A1 (ou utiliser `--votation-id`).
   c. Repérer la ligne « Total » (première ligne non vide après la ligne 7 dont la col B ≈ « Total »).
   d. Collecter les lignes de cantons : toutes les lignes dont la colonne A est un entier (1–26).
3. **Feuille Bezirke** :
   a. La ligne 7 contient l'en-tête.
   b. Collecter toutes les lignes dont la colonne A est une chaîne non vide (nom du district).
   c. Reconstruire l'appartenance cantonale en suivant l'ordre d'apparition des districts (les districts sont groupés par canton dans le même ordre que la feuille Kantone).
4. Calculer le résultat (accepté si `oui_pct > 50.0`).
5. Pour les initiatives et référendums obligatoires : compter les cantons OUI (entiers) et demi-cantons OUI (valeur ½) et indiquer si la double majorité est atteinte.
6. Produire le Markdown avec toutes les sections listées dans « Outputs ».
7. Écrire le livrable sur disque (ne pas se contenter d'une réponse dans le chat).

## Notes méthodologiques

- Les cantons numérotés à partir de la feuille Kantone correspondent aux cantons historiques (parfois différents des cantons actuels, notamment pour les demi-cantons qui apparaissent chacun séparément).
- Les colonnes D (bulletins déposés) et C (inscrits) peuvent être absentes dans la feuille Bezirke pour les votations anciennes : dans ce cas, signaler dans la section « Incertitudes ».
- Les noms de cantons et de districts dans le fichier sont en allemand (langue de la source BFS) ; les traduire en français dans la sortie pour les cantons principaux (voir tableau de correspondance ci-dessous).
- Toutes les phrases rédigées en français dans le Markdown doivent être orthographiées correctement, avec les accents et caractères typographiques français nécessaires (ex. `é`, `à`, `ç`, `œ`). Ne jamais translittérer le français en ASCII simple.

### Tableau de correspondance des noms de cantons (allemand → français)

| Allemand              | Français                    |
|-----------------------|-----------------------------|
| Zürich                | Zurich                      |
| Bern                  | Berne                       |
| Luzern                | Lucerne                     |
| Uri                   | Uri                         |
| Schwyz                | Schwytz                     |
| Obwalden              | Obwald                      |
| Nidwalden             | Nidwald                     |
| Glarus                | Glaris                      |
| Zug                   | Zoug                        |
| Freiburg / Fribourg   | Fribourg                    |
| Solothurn             | Soleure                     |
| Basel-Stadt           | Bâle-Ville                  |
| Basel-Landschaft      | Bâle-Campagne               |
| Schaffhausen          | Schaffhouse                 |
| Appenzell A. Rh.      | Appenzell Rh.-Ext.          |
| Appenzell I. Rh.      | Appenzell Rh.-Int.          |
| St. Gallen            | Saint-Gall                  |
| Graubünden / Grisons  | Grisons                     |
| Aargau                | Argovie                     |
| Thurgau               | Thurgovie                   |
| Tessin / Ticino       | Tessin                      |
| Waadt / Vaud          | Vaud                        |
| Wallis / Valais       | Valais                      |
| Neuenburg / Neuchâtel | Neuchâtel                   |
| Genf / Genève         | Genève                      |
| Jura                  | Jura                        |

