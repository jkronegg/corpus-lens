# Coûts des skills et agents de `corpus-lens` (en crédits IA)

Coût d'exécution des skills en IA credits (1 IA credit = environ 0.01 USD), lorsque le skill est invoqué dans le chat de GitHub Copilot avec la commande `/skill:<nom_du_skill> ...`.

Il n'y a pas de coût en crédits IA si le skill est invoqué directement depuis la ligne de commande via son script. Par exemple, on peut lancer l'indexation de sources avec la commande suivante:

    python -u ".agents/skills/indexer-sources/scripts/sync_sources_json.py"; 

Certains skills dont l'exécution est fréquente sont disponibles sous forme de commande BAT:

- `indexersources.bat` (pour indexer les sources dans la base SQLite)
- `db.bat` (pour gérer la base de données SQLite)

Il est intéressant de noter que l'identification des skills est très efficace. Ainsi les deux requêtes ci-dessous ont un coût similaire ce ~1 crédit IA:

- `/skill:fetch-wikipedia-article --title "Affaire des colonels"`
- `Télécharge l'article Wikipédia sur l'affaire des colonels`

Il n'est donc pas nécessaire de connaître le nom exact des skills.

## Fetch skills

| Skill | Coût d'exécution via `/skill` (IA credit) | 
| --- |-------------------------------------------|
| fetch-wikipedia-article | 1.1                                       |
| fetch-swissvote-votation-sources | 1.5                                       |
| fetch-generic-url | 2.3                                       |
| fetch-dodis-results | 2.6                                       |
| fetch-dodis-person-details | 3.0                                       |
| fetch-elitesuisse-person-details | 3.2                                       |
| fetch-dhs-article | 3.2                                       |
| fetch-enewspaper-article-content | 4.1                                       |
| fetch-enewspaper-article-list | 4.8                                       |

Ces skills sont également disponibles via la ligne de commande (CLI). Dans ce cas, il n'y a pas de coût en crédits IA.

    fetch <source> <requête> [options]

Exemples:

    fetch dhs "affaire des colonels"
    fetch wikipedia "affaire des colonels"
    fetch dodis-person "Jean Pascal Delamuraz"
    fetch elitesuisse "Thierry Pun"
    fetch enewspaper "affaire des colonels" --start-year 1900
    fetch url "https://example.com/document.pdf"
    fetch swissvote 639

## Analyse skills

| Skill | Coût d'exécution via `/skill` (IA credit) | 
| --- |-------------------------------------------|
| startup-research |                                           |
| analyse-swissvotes-votations |                                           |
| analyse-resultats-votation |                                           |
| analyse-population-suisse |                                           |
| analyse-dynamique-historique |                                           |
| analyse-champ-lexical |                                           |
| startup-research |                                           |

## Transform and indexation skills

| Skill | Coût d'exécution via `/skill` (IA credit) | 
| --- |-------------------------------------------|
| translate-markdown |                                           |
| manage-named-entities-db |                                           |
| indexer-sources | 2.5                                       |
| extract-pdf-to-md-all-sources | 2.5                                       |
| analyse-swissvotes-votations | 1.5                                       |
| extract-pdf-to-md |                                           |

