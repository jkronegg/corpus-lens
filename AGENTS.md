# AGENTS

## But

`corpus-lens` aide la recherche historique sur la Suisse :
- collecter des sources ;
- les transformer en Markdown exploitable ;
- les indexer dans `named_entities.sqlite` ;
- interroger le corpus via un workflow RAG.

## Règle centrale

Le jugement historique reste humain. Les agents servent d'assistance documentaire, avec des réponses ancrées dans les sources.

## Flux minimal

1. Collecter.
2. Transformer.
3. Indexer.
4. Interroger.
    a. lorsque tu dois faire des calculs, tu dois écrire un script qui fait le calcul (pas de calcul avec un LLM!).
5. Vérifier dans les sources.

