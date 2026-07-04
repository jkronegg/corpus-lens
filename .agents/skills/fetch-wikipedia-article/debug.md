## Paramètre d'input additionnels

- `--out-dir`: dossier de sortie Markdown (défaut: `sources/wikipedia`).
- `--dry-run`: vérifie la résolution de l'article sans écrire de fichier.

## Exécution rapide

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/fetch_wikipedia_article.py" --title "Affaire des colonels" --dry-run
```

## Test unitaire

```powershell
python -u ".agents/skills/fetch-wikipedia-article/scripts/test_fetch_wikipedia_article.py"
```

## Notes

- Le skill utilise l'API MediaWiki officielle de Wikipedia.
- Le Markdown généré conserve une structure de sections autant que possible.
- `--dry-run` est réservé au debug.