---
name: orienter-initiative-communale
description: Détermine la forme la plus adaptée (question, interpellation, postulat, motion, pétition) pour qu'une idée soit portée au Conseil communal, avec justification et vérifications de recevabilité.
capabilities:
  - procedure-guidance
  - decision-support
entity_types:
  - acte_parlementaire
  - sujet_communal
---

# Orienter une idée vers le bon instrument communal

## Objectif

Aider à choisir le meilleur véhicule institutionnel pour porter une idée au niveau communal:
- `question`
- `interpellation`
- `postulat`
- `motion`
- `pétition`

Le skill propose une recommandation argumentée, ancrée dans les sources locales (règlement du Conseil, loi cantonale, documents internes), sans se substituer à une validation juridique humaine.

## Quand utiliser ce skill ?

- Quand un conseiller (ou un groupe) veut agir sur un sujet donné mais hésite sur la forme.
- Quand il faut arbitrer entre demande d'information, demande d'étude, demande d'action, ou saisine citoyenne.
- Quand il faut vérifier d'abord si l'idée est recevable sous la forme envisagée.

## Quand ne pas utiliser ce skill ?

- Si la question porte sur une interprétation juridique contentieuse sans sources locales disponibles.
- Si le besoin principal est la rédaction complète d'un texte final prêt au dépôt (un skill dédié de rédaction sera créé plus tard).

## Inputs

- Sujet et objectif politique concret.
- Auteur principal (conseiller, groupe politique, citoyens).
- Effet recherché: information, débat public, étude, action contraignante, transmission d'une demande.
- Degré d'urgence souhaité.
- Niveau de contrainte voulu sur la Municipalité.
- Existence d'un texte déjà rédigé (optionnel).
- Sources applicables: règlement du Conseil communal, bases légales cantonales, notes internes.

Avant toute recommandation, rechercher si le sujet est déjà traité dans une source locale identifiable (règlement communal, règlement d'utilisation, tarif, directive, préavis, décision de la Municipalité, réponse antérieure, etc.).

## Processus

1. Rechercher d'abord si le sujet est explicitement mentionné dans une ou plusieurs sources locales applicables; citer le passage pertinent si trouvé.
2. Si une source locale est identifiée, déterminer d'abord quelle autorité est compétente pour l'adopter, la modifier ou y déroger (Conseil communal, Municipalité, autre organe), en s'appuyant sur la source elle-même ou sur la hiérarchie des actes.
3. Si aucune source explicite n'est trouvée, expliciter cette absence puis inférer la compétence à partir de l'objet visé, de la nature de la mesure demandée et des règles générales applicables.
4. Reformuler ensuite le besoin en une intention opérationnelle unique (ce que l'auteur veut obtenir concrètement).
5. Évaluer la recevabilité de base selon les critères locaux (compétence, forme, objet traitable).
6. Si l'objet relève clairement de la compétence de la Municipalité, écarter en priorité les instruments qui supposent une prise de position ou une action normative du Conseil si le droit local ne les admet pas pour cet objet (notamment une motion, sauf source locale expresse contraire).
7. Si l'objet vise principalement à obtenir une étude ou un rapport sur l'opportunité d'agir, privilégier le postulat.
8. Si l'objet vise une information, une explication ou un débat sans demande d'action, privilégier question ou interpellation selon le degré de formalité recherché.
9. Réserver la pétition au dernier recours, lorsque aucun des autres mécanismes à disposition du conseiller communal ne donne satisfaction.
10. Comparer les cinq instruments selon ces critères:
   - finalité principale;
   - portée politique attendue;
   - contrainte sur la Municipalité;
   - charge procédurale et délai;
   - risque d'irrecevabilité.
11. Recommander un instrument principal + 1 alternative crédible uniquement si elle reste recevable.
12. Produire une justification sourcée et une checklist de conformité avant dépôt.

## Règles de décision (heuristique)

Modification: voeu (pas d'effet) -> amendement (modification de conclusion de préavis/rapport) -> motion (projet)
Questionnement: question (réponse) -> interpellation (réponse détaillée) -> postulat (rapport)

- Choisir `question` si l'objectif est une information ponctuelle, précise et rapide.
- Choisir `interpellation` si l'objectif est d'obtenir des explications politiques formelles et d'ouvrir une discussion.
- Choisir `postulat` si l'objectif est de demander une étude/rapport sur l'opportunité d'agir (sans imposer l'action finale).
- Choisir `motion` seulement si le droit local l'autorise pour l'objet considéré et si l'objet relève bien d'une compétence sur laquelle le Conseil peut demander une action normative; sinon l'écarter.
- Choisir `pétition` en dernier recours, si aucun des autres mécanismes à disposition du conseiller communal ne donne satisfaction.

Important:
- Toujours commencer par la question: « le sujet est-il déjà réglé, mentionné ou tarifé dans une source locale ? ».
- Si oui, analyser d'abord la compétence attachée à cette source avant de raisonner à partir du seul objectif politique.
- Si non, signaler explicitement qu'on passe à une analyse par inférence de compétence.
- En cas d'incertitude, privilégier l'instrument le plus recevable et documenter le compromis.
- Si une motion paraît inadaptée parce que le sujet relève de la Municipalité, le signaler explicitement comme problème de recevabilité.
- Toujours indiquer les articles ou extraits de source qui soutiennent la recommandation.
- Si les sources se contredisent, présenter explicitement les deux lectures et demander arbitrage humain.

## Outputs

Réponse structurée en Markdown avec sections obligatoires:
1. `Recommandation principale`
2. `Alternative possible`
3. `Justification sourcée`
4. `Checklist de recevabilité`
5. `Points à valider avec le Bureau/greffe`

Dans `Justification sourcée`, préciser explicitement:
- `Source identifiée ou non`
- `Autorité compétente sur cette source`
- `Conséquence sur le choix de l'instrument`

Format de citation recommandé: `source.md#Section` ou `source.md (Page X)`.

## Références par instrument

Consulter les fiches de référence dans `assets/` avant de conclure.
- `assets/voeu.md`
- `assets/amendement.md`
- `assets/question.md`
- `assets/interpellation.md`
- `assets/postulat.md`
- `assets/motion.md`
- `assets/petition.md`

## Notes
- Ce skill fournit une aide procédurale, pas un avis juridique contraignant.

https://publication.vd.ch/publications/dgaic/aide-memoire/autorites/droit-de-proposition-des-conseillers-communaux-ou-generaux