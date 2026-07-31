## Inputs

- `--dry-run` (optionnel): Valide l'URL et détecte le type de contenu sans télécharger.
- `--max-redirects` (optionnel): Nombre maximum de redirects à suivre (défaut: 3).
- `--out-dir` (optionnel): Dossier de sortie (défaut: `sources/generic-urls`).


## Commandes

### Valider une URL (dry-run)
```powershell
python -u ".agents/skills/fetch-generic-url/scripts/fetch_generic_url.py" --url "https://example.com/article" --dry-run
```

## Notes

- Respecte les conventions du projet: MD5 pour `signature`, accents français
- Front matter YAML obligatoire pour tous les Markdown générés (incluant `date_publication` et `date_consultation`)
- Suit automatiquement max 3 redirects HTTP (configurable via `--max-redirects`)
- Les images sont liées aux documents parents via `parent_doc_id` dans la DB
