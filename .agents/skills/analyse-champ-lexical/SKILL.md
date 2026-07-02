---
name: analyse-champ-lexical
description: Analyse le champ lexical d'un ensemble de sources pour identifier les thèmes, les acteurs, les lieux, les événements et les concepts clés liés à la question de recherche.
---

# Analyse du champ lexical

## Objectif

Ce skill analyse le champ lexical (ensemble de noms, d'adjectifs et de verbes liés par leur sémantique, c'est-à-dire traitant d'un domaine commun).

L'objectif est de fournir une vue d'ensemble des éléments importants qui émergent des sources analysées, afin d'aider le chercheur à mieux comprendre comment un document est structuré et quel message les auteurs veulent faire passer.

## Processus

1. Analyse le champ lexical du fichier Markdown spécifié par l'utilisateur (fichier référencé dans le contexte de discussion ou fichier nommé), en suivant les étapes suivantes:
  - Repérage : Lire le texte et surligner tous les mots liés à un même thème
  - Classement : Regrouper les mots par thématique (ex: champ lexical de la nature, de la guerre)
  - Interprétation : Expliquer l'effet produit par ces mots (créer une ambiance, insister sur une idée).
2. Tu produis le champ lexical dans un format structuré (JSON ou Markdown) avec les catégories suivantes (même nom que le fichier spécifié, avec une extension `.cl.json` et `.cl.md`, dans le même dossier que le fichier spécifié). Les listes de mots doivent être classés par fréquence décroissante.

Si le document à analyser contient manifestement plusieurs sections ou traite de plusieurs sujets différents, tu peux faire une analyse de champ lexical par section.