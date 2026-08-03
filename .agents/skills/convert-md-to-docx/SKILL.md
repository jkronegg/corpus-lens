---
name: convert-md-to-docx
description: Convertit un fichier Markdown en document Word (.docx) en lançant le script du skill.
---

## Inputs

- `--input` : chemin vers le fichier Markdown à convertir.
- `--output` : chemin de sortie pour le fichier Word (.docx). Optionnel.

## Utilisation

```powershell
python .agents/skills/convert-md-to-docx/scripts/convert_md_to_docx.py --input "C:\chemin\vers\document.md" --output "C:\chemin\vers\document.docx"
```

