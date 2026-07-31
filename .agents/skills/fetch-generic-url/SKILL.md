---
name: fetch-generic-url
description: Télécharge des documents depuis des URLs génériques (PDF, HTML, etc.) avec support des webpages et gestion des redirects. Ne pas utiliser pour DHS, Dodis, e-newspaperarchive, elitesuisse.
capabilities:
  - url-download
  - document-extraction
  - webpage-conversion
  - image-download
entity_types:
  - document
  - webpage
  - resource
search_hints:
  document_queries:
    strategy: delegate
    delegate_to: fetch-swissvote-votation-sources
---

# Fetch Generic URL

Télécharge des documents depuis des URLs génériques et les enregistre dans `sources/` avec synchronisation automatique à la base de données `../../../named_entities.sqlite.bak`.

## Inputs

- `--url` (obligatoire): URL cible à télécharger (document direct ou webpage).
- `--document-type` (optionnel): Type de document attendu ("pdf", "html", "docx", etc.). Si fourni, recherche les liens correspondants dans la page.

## Outputs

### Téléchargement direct (document)
- Un fichier binaire (PDF, DOCX, etc.) sauvegardé dans `sources/generic-urls/`
- Enregistrement dans `source_document` avec métadonnées

### Conversion webpage sans document_type
- Un fichier Markdown avec front matter YAML dans `sources/generic-urls/`
- Images téléchargées et stockées dans `sources/generic-urls/<slug_document>/images/`
- Chaque image enregistrée comme `source_document` avec `parent_doc_id` pointant au Markdown parent
- Structure: `## Page X` pour pagination si applicable

### Extraction avec document_type
- Un ou plusieurs fichiers du type demandé
- Chaque fichier enregistré dans la base de données

## Commandes

### Télécharger un document direct
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/document.pdf"
```

### Télécharger une webpage en Markdown
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/article"
```

### Chercher et télécharger des PDFs dans une webpage
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/documents" --document-type pdf
```

## Comportement

### 1. Détection du type de contenu
- Suit les redirects HTTP (max 3 hops par défaut)
- Détermine le MIME type à partir du header Content-Type ou de l'extension du fichier

### 2. Si URL est un document direct
- Télécharge le fichier binaire vers `sources/generic-urls/`
- Génère un `signature` (MD5 du contenu du fichier)
- Enregistre dans `source_document` avec metadata

### 3. Si URL est une webpage ET `document_type` fourni
- Utilise Playwright pour charger la page (CDP mode)
- Cherche tous les liens `<a href>` pointant vers des documents du type spécifié
- Télécharge chaque document trouvé
- Suit max 3 redirects par document si nécessaire

### 4. Si URL est une webpage ET `document_type` NOT fourni
- Utilise Playwright pour charger la page (CDP mode)
- Convertit le HTML en Markdown structuré
- Télécharge les images liées (dans un sous-dossier dédié au document)
- Crée des relations parent/child dans la base de données

### 5. Gestion des images
- Téléchargées automatiquement quand convertissant une webpage
- Stockées dans `sources/generic-urls/<slug_document>/images/`
- Nommées via hash MD5 du URL pour éviter les doublons
- Enregistrées comme `source_document` avec `parent_doc_id`

## Notes

- Fais un résumé concis des actions effectuées, sans proposer d'actions supplémentaires.
- Si un problème survient ou s'il faut modifier le comportement du skill, regarde les instructions dans [debug.md](debug.md)