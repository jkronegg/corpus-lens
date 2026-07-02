---
name: translate-markdown
description: "Translate a Markdown file to a target language (default: fr) while preserving front matter and page numbering."
---

# Translate Markdown

This skill translates a Markdown file to a target language (default `fr`) while keeping document structure intact.

Use script:

`scripts/translate_markdown.py`

## Inputs
- `--input` (required): input Markdown file path.
- `--output` (optional): output Markdown file path; default is `<input>.translated.md`.
- `--target-lang` (optional): target language code, default `fr`.
- `--dry-run` (optional): run without writing output.
- `--foreground` (optional): run in current terminal (default is background).
- `--log-file` (optional): custom log file path; default is `<input>.translated.md.log`.

## Outputs
- Writes translated Markdown to `--output`.
- Preserves Markdown structure and front matter.

## Commands

Default run (background):

```powershell
python -u ".agents/skills/translate-markdown/scripts/translate_markdown.py" --input "sources/swissvotes/votation_86/debat_parlementaire.md"
```

Foreground run:

```powershell
python -u ".agents/skills/translate-markdown/scripts/translate_markdown.py" --input "sources/swissvotes/votation_86/debat_parlementaire.md" --foreground --verbose
```

Follow background progress:

```powershell
Get-Content -Wait "sources/swissvotes/votation_86/debat_parlementaire.translated.md.log"
```

