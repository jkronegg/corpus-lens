---
name: extract-pdf-to-md-all-sources
description: Scan `sources/**/*.pdf` and extract Markdown for each PDF missing a same-name `.md` file.
---

# Extract PDF to Markdown (Batch)

Ce skill parcourt récursivement `sources/**/*.pdf` et lance l'extraction Markdown unitaire (`extract_pdf_to_md`) pour chaque PDF.

## Comportement

- Si `<fichier>.md` existe déjà, le PDF est ignoré.
- Avec `--overwrite`, l'extraction est relancée même si le `.md` existe.
- Le script fait l'essentiel du traitement (scan, filtrage, exécution, résumé JSON).

## Inputs

- `--sources-root` (optionnel): racine à scanner, défaut: `<repo>/sources`
- `--overwrite` (optionnel): force la régénération des `.md` existants
- `--dry-run` (optionnel): planifie sans écrire de fichiers

## Output

- Affiche un résumé JSON (totaux + détails par fichier)
- Retour code 1 si au moins une extraction a échoué, sinon 0

## Commandes

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py"
```

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py" --overwrite
```

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py" --dry-run
```

## Note d'implémentation

Le script appelle la fonction Python unitaire:
- `extract_pdf_to_md(pdf_path: Path, md_path: Path) -> int`
depuis `\.agents\skills\extract-pdf-to-md\scripts\pdf_to_md_extractor.py`.

Le convertisseur unitaire peut appliquer un fallback OCR sur les pages sans texte exploitable, si les dépendances optionnelles sont installées.

