---
name: fetch-enewspaper-article-list
description: Liste les articles de journaux ou publicités sur e-newspaperarchives.ch (e-npa) en fonction de critères de recherche.
---

# e-newspaperarchives Fetch article list

Ce skill lance `scripts/enewspaper_fetch_results.py` pour exécuter une recherche sur e-newspaperarchives.ch, parcourir la pagination et exporter la liste des résultats
Le téléchargement du contenu des articles est géré séparément par le skill `fetch-enewspaper-article-content`.

## Inputs

Propriétés de base:

- `--query` : texte de recherche a soumettre si l'URL ne contient pas deja `txq`.
- `--lang` : langue par defaut si absente de l'URL (`fr` par defaut).
- `--start-day` : jour de la date de debut (`1-31`, optionnel).
- `--start-month` : mois de la date de debut (`1-12`, optionnel).
- `--start-year` : annee de la date de debut (optionnel).
- `--end-day` : jour de la date de fin (`1-31`, optionnel, inclus).
- `--end-month` : mois de la date de fin (`1-12`, optionnel).
- `--end-year` : annee de la date de fin (optionnel).
- `--newspaper-codes` : liste de codes de journaux a filtrer (ex: `NZZ BEZ LLE`). Si absent ou vide, recherche sur tous les journaux. Les codes correspondants au fichier `assets/enewspaper_selectpuq_journaux.csv`.

Propriétés avancées (à utiliser en cas de problème):

- `--output-dir` : dossier de sortie (defaut: `sources/enewspaper`).
- `--max-pages` : pages max a traiter (defaut: `20`).
- `--wait-time` : attente apres chargement de page (defaut: `3.5` sec).
- `--no-pause-on-challenge` : évite la pause manuelle initiale (optionnel, à utiliser seulement en cas d'échec causé par Cloudflare Turnstile).
- `--close-browser-at-end` : ferme le navigateur a la fin de la collecte (**usage exceptionnel uniquement**: dernier recours en cas de blocage technique, debug, ou exécution non interactive).
- `--dry-run` : affiche la configuration sans collecter.

## Outputs

Le script écrit par défaut dans `sources/enewspaper/` :

- `enewspaper_<requete>_<timestamp>.json`
- `enewspaper_<requete>_<timestamp>.md`

Le JSON contient les résultats structures (titre, date, journal, URL, position) et un champ `year_histogram` (mapping année -> nombre d'articles) quand disponible.
Le Markdown contient un resume global, l'histogramme temporel et les details par page.
Ce skill ne télécharge pas les pages article.

### Section Markdown ajoutée

Le fichier Markdown inclut la section:

- `## Histogramme du nombre d'articles au cours du temps`

Cette section est alimentée à partir de la page de recherche HTML, via:

- `div#searchresultyeargraph`
- attribut `data-year-count-mapping-json` (JSON année -> nombre)

Le rendu contient:

- un histogramme texte (barres ASCII)
- un tableau `Année | Nombre d'articles`

Si la donnée n'est pas disponible ou illisible, le Markdown affiche explicitement que l'histogramme est indisponible.

## Commandes

```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" `
  --query "reorganisation de l'instruction militaire" `
  --start-year 1935 `
  --start-month 1 `
  --start-day 1 `
  --end-year 1935 `
  --end-month 2 `
  --end-day 1
```

Avec filtre par journaux:

```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" `
  --query "reorganisation de l'instruction militaire" `
  --newspaper-codes NZZ BEZ LLE `
  --start-year 1935 `
  --start-month 1 `
  --start-day 1 `
  --end-year 1935 `
  --end-month 2 `
  --end-day 1
```

Dry-run pour verifier la configuration:

```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" --dry-run
```

## Notes

- Regle generale: le navigateur doit rester ouvert apres la collecte pour verification manuelle par l'historien.
- Ne pas utiliser `--close-browser-at-end` en fonctionnement normal.
- `--close-browser-at-end` n'est autorise qu'en dernier recours (incident technique, debugging, ou contexte non interactif).
- Règles date de début :
  - aucun champ (`--start-day/--start-month/--start-year`) => pas de filtre de début.
  - `--start-year` seul => recherche depuis le `01/01/<annee>`.
  - `--start-year` + `--start-month` => recherche depuis le `01/<mois>/<annee>`.
  - `--start-day` exige aussi `--start-month` et `--start-year`.
- Règles date de fin (même logique que début) :
  - aucun champ (`--end-day/--end-month/--end-year`) => pas de filtre de fin.
  - `--end-year` seul => recherche jusqu'au `01/01/<annee>`.
  - `--end-year` + `--end-month` => recherche jusqu'au `01/<mois>/<annee>`.
  - `--end-day` exige aussi `--end-month` et `--end-year`.
  - si début et fin sont fournis, la fin doit être >= début.

### Codes de journaux disponibles

Les codes de journaux valides sont definis dans le fichier `assets/enewspaper_selectpuq_journaux.csv`. Ce fichier contient deux colonnes:
- `value` : le code court du journal (ex: `NZZ`, `BEZ`, `LLE`)
- `text` : le nom du journal (ex: `Neue Zürcher Zeitung`, `Berner Zeitung`, `La liberté`)

Pour extraire les codes de journaux facilement, utilisez le script utilitaire 
`scripts/list_newspaper_codes.py`:

```powershell
# Afficher tous les journaux
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/list_newspaper_codes.py"

# Filtrer par nom (ex: tous les journaux "Berner")
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/list_newspaper_codes.py" --filter "Berner"

# Obtenir uniquement les codes (prets a etre passes a --newspaper-codes)
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/list_newspaper_codes.py" --filter "Berner" --codes-only
```

Exemple pour rechercher sur des journaux suisses allemands comme Neue Zürcher Zeitung (NZZ), Berner Zeitung (BEZ):
```powershell
--newspaper-codes NZZ BEZ
```

Ou en utilisant directement l'utilitaire:
```powershell
python -u ".agents/skills/fetch-enewspaper-article-list/scripts/enewspaper_fetch_results.py" `
  --query "justice militaire" `
  --newspaper-codes $(python ".agents/skills/fetch-enewspaper-article-list/scripts/list_newspaper_codes.py" --filter "Berner" --codes-only) `
  --start-year 1950
```

## Related files

- skill `../fetch-enewspaper-article-content/SKILL.md`
- autres sources de données en ligne `sources_en_ligne/enewspaperarchivesch.md`
