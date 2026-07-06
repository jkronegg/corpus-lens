---
name: fetch-dodis-document-content
description: Télécharge le contenu d'un document Dodis à partir de son identifiant numérique et exporte la page en Markdown.
capabilities:
  - document-lookup
  - document-content-extraction
entity_types:
  - document
search_hints:
  document_queries:
    strategy: prefer-first
    also_search:
      - fetch-dodis-results
      - fetch-dodis-person-details
---

# Dodis Fetch Document Content

Ce skill ouvre l'URL `https://dodis.ch/<identifiant>?lang=fr` dans un navigateur Playwright déjà ouvert en mode CDP, extrait le contenu du document et l'enregistre en Markdown.

Ce skill est le point d'entrée recommandé pour récupérer le contenu détaillé d'un document Dodis identifié par son numéro. Pour les recherches documentaires plus larges, utiliser `fetch-dodis-results`.

## Inputs

- `--document-id` (obligatoire): identifiant numérique Dodis du document.
- `--out-dir`: dossier de sortie Markdown (défaut: `sources/dodis/documents`).
- `--cdp-url`: endpoint CDP (défaut: `http://127.0.0.1:9222`).
- `--dry-run`: mode debug uniquement (éviter en usage standard).

## Outputs

- Si l'identifiant est invalide: message JSON explicite `found: false`, aucun fichier créé.
- Si le document est accessible: un fichier Markdown avec front matter YAML dans `sources/dodis/documents/`.

## Règle d'usage

- En usage normal, exécuter directement la commande standard (sans `--dry-run`).
- Réserver `--dry-run` aux cas de debug (diagnostic, validation rapide d'arguments).

## Commandes

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/fetch_dodis_document_content.py" --document-id 43445
```

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/fetch_dodis_document_content.py" --document-id 43445 --dry-run
```

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/test_fetch_dodis_document_content.py"
```

