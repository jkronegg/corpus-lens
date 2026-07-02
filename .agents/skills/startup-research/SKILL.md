---
name: startup-research
description: Donne un coup de pouce au chercheur afin de mettre en place les documents de base pour démarrer sa recherche.
---

# Coup de pouce pour démarrer la recherche

## Quand utiliser ce skill ?

Lorsqu'il n'y a pas beaucoup de sources, que le contexte de recherche n'est pas encore bien défini (p.ex. le chercher a seulement un thème de recherche).

## Quand ne pas utiliser ce skill ?

En fin de travail de recherche, lorsque le nombre de sources est déjà conséquent et que le chercheur a déjà une bonne idée du contexte historique.

## Processus
1. Regarde le thème de recherche dans `travail_de_recherche.md` et identifie les éléments clés (personnes, organisations, événements, lieux, etc.) qui pourraient guider la recherche de sources.
2. Utilise les skills de recherche de sources (p.ex. `fetch-swissvote-votation-sources`, `fetch-dodis-results`, `fetch-enewspaper-article-list`, `fetch-dhs-article`) pour trouver des sources pertinentes en fonction du thème de recherche.
3. Synchronise les sources avec le skill `sync_sources_json` pour les rendre disponibles à tous les agents.
4. Utilise l'agent `agent_categorisation_de_source` pour analyser les sources
5. Utilise l'agent `agent_contexte_historique` pour identifier les éléments de contexte historique liés au thème de recherche.
6. Suggère des questions pour le chercheur.