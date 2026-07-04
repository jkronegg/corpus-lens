---
name: fetch-dhs-article
description: Fetch DHS articles from bundled DHS CSV catalogs, convert them to Markdown, and download local images into the project corpus.
capabilities:
  - reference-lookup
  - person-lookup
  - concept-lookup
entity_types:
  - person
  - family
  - geography
  - concept
  - event
search_hints:
  person_queries:
    strategy: search-in-parallel
    also_search:
      - fetch-elitesuisse-person-details
---

# DHS Fetch Article

## Purpose

Fetch one or more DHS articles from local DHS catalogs and export them to the project corpus as Markdown with local images.

Implementation:

- `scripts/dhs_fetch_article.py`

## When to use

Use this skill to:

- add a new DHS notice to `sources/DHS/`
- enrich the source corpus with DHS articles from search terms
- refresh an existing DHS export (`--overwrite`)

After using this skill, do **not** verify that the articles and images are property fetched (this is already done in the scripts).

Do **not** use this skill when you need to:

- analyse the historical content of already fetched sources
- synchroniser la table `source` de `named_entities.sqlite`
- convert arbitrary PDFs to Markdown
- search external sites other than DHS

## Inputs

### Required

- one or more DHS search terms via `--term`

### Optional

- `--csv-dir`: directory containing DHS CSV catalogs
- `--csv-glob`: glob used to discover DHS CSV files
- `--out-dir`: destination directory for Markdown files and images
- `--max-hits`: maximum number of catalog matches retained per term
- `--overwrite`: overwrite existing Markdown files
- `--dry-run`: show what would be fetched without making HTTP requests
- `--timeout`: HTTP timeout in seconds
- `--sleep`: pause between requests
- `--user-agent`: custom HTTP user-agent

## Outputs

By default, the skill writes:

- one Markdown file per fetched DHS article in `sources/DHS/` by default
- one image subdirectory per fetched article under `sources/DHS/images/`

Exact naming and matching rules are defined in `scripts/dhs_fetch_article.py`.

## Required files

- `scripts/dhs_fetch_article.py`
- DHS catalogs in `assets/`

## Commands

### Preview the selected DHS hit without downloading anything

```powershell
python -u ".agents/skills/fetch-dhs-article/scripts/dhs_fetch_article.py" --term "Frontisme" --dry-run
```

### Fetch one article

```powershell
python -u ".agents/skills/fetch-dhs-article/scripts/dhs_fetch_article.py" --term "Antifascisme"
```

### Fetch multiple related articles into the corpus

```powershell
python -u ".agents/skills/fetch-dhs-article/scripts/dhs_fetch_article.py" `
  --term "Frontisme" `
  --term "Front national" `
  --term "Union nationale" `
  --term "Fascisme" `
  --term "Antifascisme" `
  --out-dir "C:\path\to\project\sources\DHS"
```

### Overwrite previously generated files

```powershell
python -u ".agents/skills/fetch-dhs-article/scripts/dhs_fetch_article.py" --term "Corporatisme" --overwrite
```

## Expected behavior

- Existing files should be preserved unless `--overwrite` is passed.
- Images should be downloaded into a per-article directory under `images/`.
- The command should print a JSON summary containing at least:
  - `terms`
  - `hits`
  - `saved`
  - `errors`

## Constraints and caveats

- This skill depends on the DHS CSV catalogs being available locally.
- Matching and selection behavior are intentionally delegated to the script implementation.
- A DHS page blocked by Cloudflare will fail with an error.
- This skill only fetches DHS notices; it does not classify or analyse them.
- Permanent execution rule: for standard DHS downloads, run the skill command directly without reading `scripts/dhs_fetch_article.py` first.
- Exception: read `scripts/dhs_fetch_article.py` only when you need to modify the DHS download behavior.
- The `out-dir` option must be used only when debugging. In most cases, use the default value.

## Related files

- skill `sync_sources_json`

