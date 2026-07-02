---
name: fetch-elitesuisse-person-details
description: Recherche une personne dans l'index CSV EliteSuisses et exporte sa fiche détaillée en Markdown.
capabilities:
  - person-lookup
  - notable-figures
entity_types:
  - person
search_hints:
  person_queries:
    strategy: prefer-first
    also_search:
      - fetch-dhs-article
---

# EliteSuisses Fetch Person Details

## But

Ce skill sert à rechercher une personne dans un index CSV local EliteSuisses, puis à télécharger sa fiche détaillée et la sauvegarder en Markdown dans `sources/elitesuisses/`.

Script principal:

- `scripts/fetch_elitesuisse_person_details.py`
- Test unitaire: `scripts/test_fetch_elitesuisse_person_details.py`

## Assets inclus

- `assets/elitessuisses_personnes_A_Z.csv` (index des personnes A-Z)
- `assets/elitessuisses_index_export.py` (script d'export de l'index A-Z)

## Entrées

### Obligatoire

- `--name`: nom de la personne recherchée (ex: `"Albert Aa, von der"`)

### Optionnelles

- `--csv-path`: chemin du CSV d'index (défaut: asset du skill)
- `--out-dir`: dossier de sortie Markdown (défaut: `sources/elitesuisses`)
- `--cdp-url`: endpoint CDP (défaut: `http://127.0.0.1:9222`)
- `--candidate-index`: choix 1-based si plusieurs correspondances
- `--exact`: impose une correspondance stricte sur `prénom + nom`
- `--dry-run`: vérifie la correspondance sans écrire de fichier

## Sorties

- Si personne non trouvée: sortie JSON avec `found: false` et message explicite.
- Si personne trouvée: fichier Markdown dans `sources/elitesuisses/` avec front matter YAML:
  - `title`
  - `date`
  - `author`
  - `sources`

## Commandes

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/fetch_elitesuisse_person_details.py" --name "Albert Aa, von der" --dry-run
```

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/fetch_elitesuisse_person_details.py" --name "Albert Aa, von der"
```

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/fetch_elitesuisse_person_details.py" --name "Jean Dupont" --exact
```

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/smoke_test_fetch_elitesuisse_person_details.py"
```

## Comportement attendu

- Le script lit l'index CSV local.
- Si la personne est absente, il le dit explicitement.
- Si la personne est présente, il ouvre l'URL de la fiche et exporte les sections visibles en Markdown.
- Le Markdown produit est structuré avec `## Page 1` pour être compatible avec les contraintes d'indexation des sources.

## Contraintes

- Dépend d'un navigateur CDP déjà disponible (souvent nécessaire à cause de Cloudflare).
- N'analyse pas le contenu historique: il se limite à la collecte et conversion en source Markdown.
- Règle d'usage: exécuter d'abord la commande du skill; lire/modifier le script seulement si le comportement doit changer.
- Après chaque modification du skill, exécuter le test unitaire avant de valider les changements.

