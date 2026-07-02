---
name: analyse-dynamique-historique
description: Analyse les possibles régimes de temporalité (ou dynamique historique), donc les stabilités, continuités et ruptures dans une source.
---
# Analyse des continuités et ruptures

## Objectif

Tu analyses l'entièreté du document spécifié pour trouver:

- des signaux de stabilité (inertie, tradition, héritage)
- des signaux de continuité (évolution lente)
- des signaux de rupture (changement, crise, basculement)

Important:
- tu analyses un discours sur le changement (comment ce document fabrique, suggère ou masque le changement), pas le changement lui-même.
- tu analyses l'intégralité du document
- lorsque tu cites une source, indique le numéro de page.

## Entrée
Document brut (texte, archive, discours, lettre, etc.): spécifié par l'utilisateur ou référencé dans le contexte de discussion.
Métadonnées (date, auteur, contexte si dispo).

## Sortie

Tu dois toujours produire les livrables sur disque. Ne te contente jamais d'une réponse dans le chat.

### Sortie attendue pour un document source unique

Produit systématiquement un fichier JSON avec le même nom que le fichier spécifié, avec une extension `.dynamique.json` dans le même dossier que le fichier spécifié:

```json
{
  "dynamiques_historiques": [
    {
      "champ_lexical": ["stabilité", "héritage"],
      "extraits": ["..."],
      "domaines": ["institutionnelle", "culturelle"],
      "vitesse": 20,
      "auteur": {
        "position": "réticent au changement",
        "arguments": ["références à des événements historiques"],
        "niveau_confiance": "30%",
        "biais_possibles": ["omission d'une rupture majeure"],
        "incoherences": ["contradiction avec d'autres sources"],
        "malhonnetete_intellectuelle" : ["..."]        
      }
    }
  ],
  "synthese": {
    "lecture_generale": "...",
    "recommandations_methodologiques_pour_le_chercheur": [
      "..."
    ]
  }
}
```

Contraintes:
- le fichier est trié par vitesse de changement décroissante.

Produit systématiquement aussi un fichier Markdown avec le même nom de fichier que la source et l'extension `.dynamique.md`.
Le fichier est placé dans le même dossier.
Le fichier de sortie Markdown suit la structure du fichier JSON, mais dans une forme lisible pour un humain.
Toutes les phrases rédigées en français dans le Markdown doivent être orthographiées correctement, avec les accents et caractères typographiques français nécessaires (ex. `é`, `à`, `ç`, `œ`). Ne jamais translittérer le français en ASCII simple.
Le fichier de sortie Markdown contient un front matter Yaml avec les champs suivants:
- `title`: "Analyse de la dynamique historique de <nom du document>"
- `date`: date de l'analyse
- `author`: "skill analyse-dynamique-historique"
- `sources`: liste des sources citées dans l'analyse

Lorsque l'analyse dynamique historique porte sur plusieurs documents source:
- l'analyse dynamique historique est basée sur l'ensemble des analyses dynamiques historiques du corpus mentionné par le demandeur.
- tu dois produire un **unique** couple de fichiers de sortie pour le corpus entier: un JSON et un Markdown.
- les fichiers de sortie doivent être écrits dans `sortie/` avec le nom `analyse_dynamique_historique_<qualificatif_corpus>.json` et `analyse_dynamique_historique_<qualificatif_corpus>.md`.
- ne réponds pas seulement dans le chat: le livrable est considéré incomplet tant que ces deux fichiers n'existent pas sur disque.

## Processus

1. Lire attentivement le document en question, en prêtant une attention particulière aux passages qui évoquent des changements, des continuités ou des ruptures.
   - Indices de stabilité
     - Champ lexical de la stabilité ("tradition", "immuable", "maintenir", "conserver", référence aux ancêtres lointains)
     - Références au passé comme modèle ("comme toujours...", "dans la tradition...")
     - Stabilité des institutions ou des pratiques ("inertie", "maintien")
     - Naturalisation ("il est normal que...")
   - Indices de continuité (évolution lente)
     - Champ lexical de l'évolution lente ("évolution", "changement", "adaptation", "progressivement", "transitoire")
     - Evolution chiffrée
   - Indices de rupture
     - Champ lexical de la crise ("nouveau", "fin de...", "révolution", "abolir", "crise", "urgence", "crise")
     - Rupture normative ("désormais...", "plus jamais...", "changement", "transition")
     - Désignation d’un avant / après
2. Identifie le type de continuité ou de rupture:
   - Classification par domaines et attribution multi-domaines
     - Politique : "groupe de contact", "Chambres", "motion", "répartition des tâches"
     - Sociale : "sécurité sociale", "bourses", "maisons de retraite", "santé"
     - Économique : "péréquation financière", "budget", "subventions", montants en francs.
     - Culturelle : "conservation des monuments", "culture", "sensibilité régionale", "régional"
     - Institutionnelle "constitution", "commune", "canton", "Confédération", "loi-cadre", "fédéralisme"
     - Technologique : "évolution technique", référence à la science
- Vitesse de la dynamique historique (variable entre 0 et 100). 
     - Méthode d'estimation (score composite) :
       - Indicateurs lexicaux (poids 35%) : intensité des mots de rupture/extrême (ex. "désormais", "réviserimmédiatement" → +70).
       - Temporalité explicite (poids 25%) : délais mentionnés (ex. "1984", "fin 1985") → modère vitesse plans/transition = moyenne).
       - Modalité argumentative (poids 20%) : impératifs/ordre vs hypothèses → ordre = plus rapide.
       - Portée institutionnelle (poids 10%) : révision constitutionnelle simultanée → plus élevée.
       - Fréquence & densité (poids 10%) : répétition de termes de changement.
    - Barèmes indicatifs:
      - 0–10 : stabilité forte (texte insiste sur continuité, absence d'actions immédiates).
      - 11–40 : continuité lente / adaptations minimales.
      - 41–70 : changement programmé / évolution organisée (mesures avec calendrier).
      - 71–90 : accélération / mesures urgentes, procédures uniphase.
      - 91–100 : rupture rapide / langage révolutionnaire ou urgence extrême.
  3. Analyse comment l'auteur présente des continuités et ruptures
  - Favorable au changement
  - Réticent au changement
4. Analyse comment l’auteur construit ces idées de continuité ou de rupture
   - Arguments utilisés
     - Références à des événements ou des figures historiques
     - Appels à l’émotion ou à la raison
   - Niveau de confiance
     - Faible : indices implicites
     - Moyen : indices linguistiques clairs
     - Élevé : argumentation structurée
5. Analyse critique de la position de l'auteur afin de détecter:
    - Biais possibles
    - Incohérences internes
    - Contradictions avec d'autres sources
    - Omissions importantes (ex: ne pas mentionner une rupture majeure qui aurait dû être mentionnée, par manque de connaissance ou volontairement)
    - Malhonnêteté intellectuelle (ex: présenter une rupture comme une continuité, ou inversement, pour servir un agenda politique ou idéologique)
      - Discursive (changement dans le langage, mais sans changement réel)
      - Symbolique (changement dans les symboles, mais pas dans les pratiques)
6. Suggère des tâches au chercheur afin de clarifier les zones d'ombre, p.ex.
    - Questions à clarifier
    - Suggestion de sources supplémentaires à télécharger pour aider à la clarification (p.ex. DHS)
7. Synthétise les résultats de ton analyse dans un format structuré (JSON et Markdown, voir rubrique "Sortie" ci-dessus)

Précisions:
- Lorsque tu évalues le domaine institutionnel (commune/canton/confédération), évalue la situation sous plusieurs principes:
  - transfert de charges et responsabilités 
  - fédéralisme: les unités de l'ensemble (p.ex. commune, canton) sont souveraines
  - solidarité: les unités de l'ensemble se soutiennent mutuellement (p.ex. péréquation)
  - subsidiarité: les tâches que les unités de l'ensemble ne peuvent assumer seules sont déléguées à l'échelon supérieur
- Lorsque tu évalues le domaine culturel, tient compte des éléments suivants:
  - différence ville - campagne
  - 4 langues nationales officielles (français, allemand, italien, romanche)
  - population multi-culturelle (proportion très variable selon les cantons : 1-35%)