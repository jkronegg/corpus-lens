# Indexation des documents source

Indexe les documents du répertoire `sources` dans la base de données.

1. Correction des incohérences entre les fichiers et la base de données:
- fichiers déplacés
- fichiers renommés
- fichiers supprimés
2. Extraction du texte des fichiers PDF et conversion en Markdown
3. Mise à jour de la base de données avec les métadonnées extraites des fichiers PDF et les chemins vers les fichiers Markdown générés.
4. Recherche d'entités nommées dans le texte Markdown (nom de personnes).
