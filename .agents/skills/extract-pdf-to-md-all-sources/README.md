# extract-pdf-to-md-all-sources

Batch skill to extract all PDFs under `sources/**/*.pdf` into Markdown by calling the unit extractor `extract_pdf_to_md`.

## Run

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py"
```

## Force regeneration

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py" --overwrite
```

## Dry run

```powershell
python -u ".agents/skills/extract-pdf-to-md-all-sources/scripts/extract_pdf_to_md_all_sources.py" --dry-run
```

