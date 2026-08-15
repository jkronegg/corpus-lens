# analyse-cadastre-energetique

Skill scriptable pour interroger la base `regener` du cadastre energetique vaudois avec des questions en langage naturel.
Source des données : https://viageo.ch/md/902dbc63-af5f-4bd2-9de5-3417ab664c40

## Fichiers

- `SKILL.md` : mode d'emploi du skill
- `scripts/analyse_cadastre_energetique.py` : script principal
- `assets/Cadastre_energetique_des_batiments_vaudois_103-VD.1.gpkg` : base de donnees GeoPackage
- `assets/MGDM_103VD_EnergetiqueBatiments_V1.1.2.md` : description des colonnes/modeles

## Test rapide

```powershell
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "top 5 communes par co2"
```

## Sortie Markdown

```powershell
python -u ".agents/skills/analyse-cadastre-energetique/scripts/analyse_cadastre_energetique.py" --question "analyse mazout" --output "initiatives/world_model_mazout/analyse_mazout_skill.md"
```

