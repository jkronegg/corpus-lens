---
name: fetch-generic-url
description: Télécharge des documents depuis des URLs génériques (PDF, HTML, etc.) avec support des webpages et gestion des redirects.
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

Télécharge des documents depuis des URLs génériques et les enregistre dans `sources/` avec synchronisation automatique à la base de données `named_entities.sqlite`.

## Inputs

- `--url` (obligatoire): URL cible à télécharger (document direct ou webpage).
- `--document-type` (optionnel): Type de document attendu ("pdf", "html", "docx", etc.). Si fourni, recherche les liens correspondants dans la page.
- `--out-dir` (optionnel): Dossier de sortie (défaut: `sources/generic-urls`).
- `--dry-run` (optionnel): Valide l'URL et détecte le type de contenu sans télécharger.
- `--max-redirects` (optionnel): Nombre maximum de redirects à suivre (défaut: 3).
- `--follow-links` (optionnel): Si true et aucun document_type, récupère également les ressources liées (images).

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
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/article" --follow-links
```

### Chercher et télécharger des PDFs dans une webpage
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/documents" --document-type pdf
```

### Valider une URL (dry-run)
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/article" --dry-run
```

## Comportement

### 1. Détection du type de contenu
- Suit les redirects HTTP (max 3 hops par défaut)
- Détermine le MIME type à partir du header Content-Type ou de l'extension du fichier
- Valide l'accessibilité et la taille du fichier

### 2. Si URL est un document direct
- Télécharge le fichier binaire vers `sources/generic-urls/`
- Génère un `identifiant_technique` (MD5 du contenu du fichier)
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
- Téléchargées uniquement si `--follow-links` ou quand convertissant une webpage
- Stockées dans `sources/generic-urls/<slug_document>/images/`
- Nommées via hash MD5 du URL pour éviter les doublons
- Enregistrées comme `source_document` avec `parent_doc_id`

## Notes

- Utilise Playwright en mode CDP (Chrome DevTools Protocol) pour les webpages interactives
- Respecte les conventions du projet: MD5 pour `identifiant_technique`, accents français
- Front matter YAML obligatoire pour tous les Markdown générés (incluant `date_publication` et `date_consultation`)
- Suit automatiquement max 3 redirects HTTP (configurable via `--max-redirects`)
- Les images sont liées aux documents parents via `parent_doc_id` dans la DB

