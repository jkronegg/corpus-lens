# fetch-dodis-person-details

Recherche locale d'une personne Dodis via `assets/persons.csv` puis export de la page référencée en Markdown.

## Fichiers

- `SKILL.md`
- `assets/persons.csv`
- `assets/fetch_dodis_persons_csv.py`
- `scripts/fetch_dodis_person_details.py`
- `scripts/test_fetch_dodis_person_details.py`
- `assets/test_fetch_dodis_persons_csv.py`

## Exécution rapide

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/fetch_dodis_person_details.py" --name "Jean Dupont"
```

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/fetch_dodis_person_details.py" --name "Jean Dupont" --dry-run
```

`--dry-run` est réservé au debug (diagnostic), pas au flux normal.

## Test unitaire

```powershell
python -u ".agents/skills/fetch-dodis-person-details/scripts/test_fetch_dodis_person_details.py"
```

```powershell
python -u ".agents/skills/fetch-dodis-person-details/assets/test_fetch_dodis_persons_csv.py"
```

## Construire l'index Dodis des personnes

```powershell
python -u ".agents/skills/fetch-dodis-person-details/assets/fetch_dodis_persons_csv.py"
```

Le script mémorise la progression dans `assets/fetch_dodis_persons_state.json` et reprend automatiquement depuis la dernière page validée.

