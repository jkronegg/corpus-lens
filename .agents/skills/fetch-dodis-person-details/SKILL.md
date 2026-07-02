---
name: fetch-dodis-person-details
description: Recherche Dodis orientée personnes (c=Person) via index local et export de la fiche en Markdown.
capabilities:
  - person-lookup
  - person-search
entity_types:
  - person
search_hints:
  person_queries:
    strategy: prefer-first
    also_search:
      - fetch-dhs-article
      - fetch-elitesuisse-person-details
  document_queries:
    strategy: delegate
    delegate_to: fetch-dodis-results
---

# Dodis Fetch Person Details

Ce skill recherche une personne dans `assets/persons.csv` (index local), puis ouvre l'URL associée via un navigateur Playwright déjà ouvert en mode CDP et enregistre le contenu en Markdown.

Ce skill est le point d'entrée recommandé pour les requêtes Dodis sur des personnes. Pour les recherches de documents, utiliser `fetch-dodis-results`.

## Inputs

- `--name` (obligatoire): nom complet à rechercher.
- `--persons-csv`: chemin CSV local (défaut: `assets/persons.csv`).
- `--out-dir`: dossier de sortie Markdown (défaut: `sources/dodis/persons`).
- `--cdp-url`: endpoint CDP (défaut: `http://127.0.0.1:9222`).
- `--dry-run`: mode debug uniquement (éviter en usage standard).

## Outputs

- Si la personne n'est pas trouvée: message JSON explicite `found: false`, aucun fichier créé.
- Si la personne est trouvée: un fichier Markdown avec front matter YAML dans `sources/dodis/persons/`.

## Règle d'usage

- En usage normal, exécuter directement la commande standard (sans `--dry-run`).
- Réserver `--dry-run` aux cas de debug (diagnostic, test de matching, validation rapide d'arguments).

## Assets

- `assets/persons.csv`: index local des personnes Dodis, colonnes:
  - `prénom`
  - `nom`
  - `année de naissance`
  - `année de décès`
  - `URL`
- `assets/fetch_dodis_persons_csv.py`: script de peuplement de `persons.csv` depuis Dodis avec reprise après échec via fichier d'état.

## Commandes

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/fetch_dodis_person_details.py" --name "Jean Dupont"
```

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/fetch_dodis_person_details.py" --name "Jean Dupont" --dry-run
```

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/test_fetch_dodis_person_details.py"
```

```powershell
python -u ".agents/skills/fetch-dodis-person-details/assets/fetch_dodis_persons_csv.py"
```

