# analyse-consommation-pv-batterie

Skill de pré-dimensionnement PV+batterie à partir d'une consommation quart-horaire.

## Installation

```powershell
pip install -r ".agents/skills/analyse-consommation-pv-batterie/requirements.txt"
```

## Exécution rapide

```powershell
python -u ".agents/skills/analyse-consommation-pv-batterie/scripts/analyse_consommation_pv_batterie.py" --input-csv "sources/romande-energie/jk_kronegg_ch/romande_energie_quarter_hourly.csv" --panels-south 24 --panels-east 12 --panels-west 12 --battery-kwh-list "5,10,15,20" --output "sortie/analyse_pv_batterie.md"
```

Si au moins un des paramètres `--panels-north`, `--panels-south`, `--panels-east`, `--panels-west` est fourni avec une valeur > 0, le script simule la configuration réelle de toiture correspondante. Sinon, il retombe sur le mode legacy `--pv-kwp-list`.

## Lancer les tests

```powershell
python -m unittest discover -s ".agents/skills/analyse-consommation-pv-batterie/tests" -p "test_*.py" -v
```


