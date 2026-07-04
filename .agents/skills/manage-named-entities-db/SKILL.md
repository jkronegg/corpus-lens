---
name: manage-named-entities-db
description: Gère la base de données SQLite des entités nommées (personnes, mentions). Permet d'ajouter/mettre à jour des personnes, d'enregistrer des mentions dans les sources, de rechercher des entités et d'exporter leurs données.
capabilities:
  - person-upsert
  - mention-add
  - source-list
  - person-search
  - mention-search
  - db-stats
  - person-export
entity_types:
  - person
  - named_entity
db:
  path: sources/named_entities.sqlite
  schema: .agents/skills/manage-named-entities-db/assets/schema.sql
  init_script: .agents/skills/manage-named-entities-db/scripts/init_db.py
---

# Manage Named Entities DB

Ce skill gère la base de données SQLite du projet (`named_entities.sqlite`). Il s'appuie sur le schéma défini dans `.agents/skills/manage-named-entities-db/assets/schema.sql`.

La base est une **source secondaire dérivée** : elle centralise les mentions de personnes (et à terme d'autres entités) extraites des fichiers Markdown du répertoire `sources/`, ainsi que l'index canonique des sources via la table `source`.

## Sous-commandes

| Sous-commande    | Action                                                        |
|------------------|---------------------------------------------------------------|
| `upsert-person`  | Ajoute ou met à jour une personne (idempotent sur `key`)      |
| `add-mention`    | Ajoute une mention d'une entité dans une source               |
| `search-person`  | Recherche une personne par nom ou alias (fuzzy)               |
| `list-mentions`  | Liste les mentions d'une personne ou d'une source             |
| `list-sources`   | Liste les sources indexées dans la table `source`             |
| `list-source-documents` | Liste les documents indexés dans `source_document`     |
| `stats`          | Affiche des statistiques globales sur la base                 |
| `export-person`  | Exporte une personne et ses mentions en JSON                  |
| `merge-persons`  | Fusionne deux personnes (transfert des mentions + alias)      |
| `reset-ner-analysis` | Supprime toutes les mentions et repasse `ner_status` de `2` à `1` |

## Inputs communs

- `--db` : chemin vers la base SQLite (défaut: `named_entities.sqlite`)

## Inputs par sous-commande

### `upsert-person`
- `--key` (obligatoire) : clé métier stable (ex. `karl_egli_1865`)
- `--display-name` (obligatoire) : nom affiché (ex. `Karl Egli`)
- `--aliases` : liste d'alias séparés par des espaces (ex. `"Egli, Karl"` `"Colonel Egli"`)

### `add-mention`
- `--person-key` (obligatoire) : clé métier de la personne
- `--source` (obligatoire) : chemin relatif du fichier source depuis `sources/` (ex. `DHS/colonels_dhs_017332.md`)
- `--page` (obligatoire) : numéro de page (`## Page X`)
- `--line-start` : numéro de ligne début (optionnel)
- `--line-end` : numéro de ligne fin (optionnel)
- `--quote` : extrait de texte (optionnel)
- `--event-date` : date contextuelle ISO 8601 (optionnel, ex. `1916-01-11`)
- `--extractor` : source de l'extraction (`manual`, `spacy`, `llm`, `rule`, `import` — défaut: `manual`)
- `--confidence` : score de confiance 0.0–1.0 (optionnel)

### `search-person`
- `--name` (obligatoire) : nom ou alias à rechercher (matching insensible à la casse)
- `--limit` : nombre max de résultats (défaut: 10)

### `list-mentions`
- `--person-key` : filtrer par clé de personne
- `--source` : filtrer par fichier source
- `--limit` : nombre max de résultats (défaut: 50)

### `list-sources`
- `--identifiant-technique` : filtre par identifiant technique exact
- `--url` : filtre par URL exacte (tolérance sur le slash final)
- `--origine` : filtre par origine (contains)
- `--limit` : nombre max de sources renvoyées (défaut: 50)

### `list-source-documents`
- `--ner-status` : filtre exact sur `source_document.ner_status` (`0`, `1`, `2`)
- `--source` : filtre texte sur `path`, `identifiant_source` ou `titre`
- `--limit` : nombre max de documents renvoyés (défaut: 50)

### `export-person`
- `--person-key` (obligatoire) : clé métier de la personne
- `--out` : fichier JSON de sortie (défaut: stdout)

### `stats`
Aucun argument spécifique.

### `reset-ner-analysis`
Aucun argument spécifique.

## Outputs

Toutes les sous-commandes émettent un objet JSON sur stdout :

- `upsert-person` → `{"action": "created"|"updated", "person_id": ..., "key": ...}`
- `add-mention` → `{"action": "created"|"skipped", "mention_id": ..., "reason": ...}`
- `search-person` → `{"results": [{"person_id", "key", "display_name", "aliases_names", "mention_count"}, ...]}`
- `list-mentions` → `{"mentions": [{"mention_id", "person_key", "person_name", "source", "page", ...}, ...]}`
- `list-sources` → `{"sources": [{"identifiant_source", "titre", "origine", ...}, ...]}`
- `list-source-documents` → `{"source_documents": [{"id", "path", "parent_doc_id", "ner_status", ...}, ...]}` (origine si `parent_doc_id=null`, dérivé sinon)
- `stats` → `{"persons": ..., "mentions": ..., "sources": ..., "extractors": {...}}`
- `export-person` → objet JSON complet personne + `mentions` + `mention_count`
- `reset-ner-analysis` → `{"action": "reset_ner_analysis", "deleted_mentions": ..., "deleted_persons": ..., "deleted_named_entities": ..., "updated_source_documents": ...}`

## Règles d'usage

- Toujours utiliser `--key` stable et normalisée (ex. `prenom_nom_annee_naissance`).
- `add-mention` est idempotent : une mention identique est ignorée silencieusement (`action: skipped`).
- La base doit être initialisée avant usage via `python -u ".agents/skills/manage-named-entities-db/scripts/init_db.py"`.

## Commandes

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" upsert-person --key "karl_egli_1865" --display-name "Karl Egli" --aliases "Egli, Karl" "Colonel Egli"
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" add-mention --person-key "karl_egli_1865" --source "DHS/colonels_dhs_017332.md" --page 1 --line-start 17 --quote "Egli" --event-date "1916-01-11"
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" search-person --name "Egli"
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" list-mentions --person-key "karl_egli_1865"
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" list-sources --limit 20
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" list-source-documents --ner-status 2 --limit 20
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" stats
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" export-person --person-key "karl_egli_1865"
```

```powershell
python -u ".agents/skills/manage-named-entities-db/scripts/manage_named_entities_db.py" reset-ner-analysis
```

