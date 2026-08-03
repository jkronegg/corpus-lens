# convert-md-to-docx

## Fonctionnement

Ce skill sert uniquement à exécuter le script de conversion Markdown vers Word.

### Script

- `scripts/convert_md_to_docx.py`

### Entrée

- un fichier Markdown UTF-8 via `--input`
- un chemin de sortie `.docx` optionnel via `--output`

### Sortie

- un document Word `.docx`

### Exemple

```powershell
python .agents/skills/convert-md-to-docx/scripts/convert_md_to_docx.py --input "C:\chemin\vers\document.md" --output "C:\chemin\vers\document.docx"
```

### Règle

Si `--output` est absent, le script crée un `.docx` avec le même nom que le Markdown.


