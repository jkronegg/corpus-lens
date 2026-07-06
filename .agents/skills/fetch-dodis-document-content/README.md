# fetch-dodis-document-content

Télécharge le contenu d'un document Dodis depuis `https://dodis.ch/<identifiant>?lang=fr` et l'exporte en Markdown.

## Fichiers

- `SKILL.md`
- `scripts/fetch_dodis_document_content.py`
- `scripts/test_fetch_dodis_document_content.py`

## Exécution rapide

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/fetch_dodis_document_content.py" --document-id 43445
```

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/fetch_dodis_document_content.py" --document-id 43445 --dry-run
```

`--dry-run` est réservé au debug (diagnostic), pas au flux normal.

## Test unitaire

```powershell
python -u ".agents/skills/fetch-dodis-document-content/scripts/test_fetch_dodis_document_content.py"
```

