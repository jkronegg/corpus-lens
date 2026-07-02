---
name: extract-pdf-to-md
description: Extrait le texte d'un PDF en Markdown paginé avec front matter YAML.
---

# Extract PDF to Markdown

Ce skill convertit un PDF en fichier Markdown en utilisant le script:
- `scripts/pdf_to_md_extractor.py`

Le script applique un fallback OCR sur les pages scannées ou vides quand les bibliothèques optionnelles sont disponibles (`PyMuPDF` + `rapidocr-onnxruntime`).

La fonction Python à appeler est:
- `extract_pdf_to_md(pdf_path: Path, md_path: Path | None = None, *, no_translate: bool = False) -> int`

## Inputs

- `pdf_path` (requis): chemin vers le fichier PDF source.
- `md_path` (optionnel): chemin vers le fichier Markdown de sortie. Par défaut: même chemin que `pdf_path` avec l'extension `.md`.
- `no_translate` (optionnel, défaut `False`): si `True`, désactive le déclenchement automatique de la traduction après extraction. Utile lors du débogage pour éviter des appels réseau superflus.
- `page_numbers` (optionnel) n'est pas une entrée standard du skill: c'est un paramètre interne de la fonction Python, à n'utiliser que pour du débogage ciblé sur quelques pages physiques du PDF.

## Outputs

- Écrit un fichier Markdown paginé avec sections `## Page X`.
- Si une page PDF ne fournit pas de texte exploitable, tente un OCR de secours.
- Ajoute un front matter YAML contenant:
  - `titre`
  - `source`
  - `date_extraction`
  - `pages`
  - `author`
  - `language_distribution`
- Retourne le nombre de pages extraites (`int`).

## Commande (PowerShell)

```powershell
python -u -c "
import importlib.util
from pathlib import Path

script_path = Path(r'.agents/skills/extract-pdf-to-md/scripts/pdf_to_md_extractor.py').resolve()
spec = importlib.util.spec_from_file_location('pdf_to_md_extractor', script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

pdf_path = Path(r'sources/swissvotes/votation_86/message_conseil_federal.pdf').resolve()

pages = module.extract_pdf_to_md(pdf_path)
print(f'ok: {pages} pages extraites vers {pdf_path.with_suffix(".md")}')
"
```

### Avec `no_translate` (débogage)

```powershell
python -u -c "
import importlib.util
from pathlib import Path

script_path = Path(r'.agents/skills/extract-pdf-to-md/scripts/pdf_to_md_extractor.py').resolve()
spec = importlib.util.spec_from_file_location('pdf_to_md_extractor', script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

pdf_path = Path(r'sources/swissvotes/votation_86/message_conseil_federal.pdf').resolve()

pages = module.extract_pdf_to_md(pdf_path, no_translate=True)
print(f'ok: {pages} pages extraites vers {pdf_path.with_suffix(".md")}')
"
```

## Exemple (Python)

```python
import importlib.util
from pathlib import Path

script_path = Path(r".agents/skills/extract-pdf-to-md/scripts/pdf_to_md_extractor.py").resolve()
spec = importlib.util.spec_from_file_location("pdf_to_md_extractor", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

pdf_path = Path("sources/swissvotes/votation_86/message_conseil_federal.pdf")

pages = module.extract_pdf_to_md(pdf_path)
print(f"{pages} pages extraites")

# Sans traduction automatique (débogage)
pages = module.extract_pdf_to_md(pdf_path, no_translate=True)
print(f"{pages} pages extraites (traduction désactivée)")
```

## Notes

- Le script est conçu pour être autonome au niveau extraction PDF -> Markdown.
- Le front matter inclut `author` et `language_distribution` pour compatibilité avec le pipeline de synchronisation.
- `page_numbers` doit rester réservé aux usages de débogage; pour une extraction normale, laisser le script traiter toutes les pages du PDF.
- Pour l’OCR, installer les dépendances optionnelles du skill dans l’environnement Python.

