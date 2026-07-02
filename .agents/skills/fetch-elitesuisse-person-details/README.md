# fetch-elitesuisse-person-details

Skill pour rechercher une personne dans l'index CSV EliteSuisses et exporter sa fiche détaillée en Markdown.

## Arborescence

- `SKILL.md` : documentation opérationnelle
- `scripts/fetch_elitesuisse_person_details.py` : script principal
- `assets/elitessuisses_personnes_A_Z.csv` : index local des personnes
- `assets/elitessuisses_index_export.py` : script d'export de l'index

## Exécution rapide

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/fetch_elitesuisse_person_details.py" --name "Albert Aa, von der"
```

## Test unitaire

```powershell
python -u ".agents/skills/fetch-elitesuisse-person-details/scripts/smoke_test_fetch_elitesuisse_person_details.py"
```

