---
name: aide-redaction-postulat
description: Accompagne un conseiller communal dans la préparation d'un postulat (phase de démarrage + vérification avant dépôt), sans rédiger le texte à sa place. À utiliser uniquement avant le dépôt, la recevabilité ou l'inscription à l'ordre du jour. Ne pas utiliser pour la défense d'un texte déjà inscrit à l'ordre du jour.
capabilities:
  - procedure-guidance
  - critical-evaluation
entity_types:
  - postulat
  - conseiller_communal
---

# Aide à la rédaction d'un postulat

## Objectif

Aider un conseiller communal à:
- se remettre rapidement dans la logique de rédaction d'un postulat;
- tester la solidité de son texte avant dépôt;
- identifier des améliorations concrètes qui augmentent ses chances de succès.

Le skill n'écrit pas le postulat à la place de l'auteur. Il structure, challenge et évalue.

## Quand utiliser ce skill ?

- Quand un conseiller veut préparer un postulat sans perdre de temps sur la forme.
- Quand un brouillon existe et qu'il faut le challenger avant dépôt.
- Quand on veut séparer le rôle d'auteur politique et le rôle d'appui méthodologique.
- Avant la recevabilité, avant l'inscription à l'ordre du jour, ou avant une première version prête pour validation.

## Quand ne pas utiliser ce skill ?

- Si l'objectif est la défense orale d'un initiative déjà inscrite à l'ordre du jour.
- Si l'initiative est déjà en phase de séance publique et de débat politique.
- Si l'objectif est la redaction complète d'un texte prêt à signer, à la place de l'auteur.
- Si la demande porte uniquement sur le choix de l'instrument (sans brouillon à évaluer).

## Règle d'orientation obligatoire

Si l'intention ne correspond pas clairement à une demande d'étude/rapport (logique du postulat), lancer d'abord le skill:
- `orienter-initiative-communale`

Ne poursuivre la phase `grill me` en mode postulat que si ce skill confirme que le postulat est approprié (ou reste l'option la plus recevable).

## Phase 1 - Démarrage

But: faciliter la prise en main quand on ne rédige pas des postulats tous les jours.

Utiliser comme base:
- `assets/postulat_canevas.md`

Sortie attendue:
1. checklist de préparation (ce qui manque avant d'écrire);
2. plan de postulat pré-rempli en puces (sans rédaction finale);
3. points de vigilance de recevabilité à vérifier avant dépôt.

### Phase 2 - Grill me

But: stress-test du postulat rédigé par le conseiller.

Evaluer successivement:
1. recevabilité probable par le Bureau du Conseil;
2. probabilité d'inscription à l'ordre du jour;
3. probabilité d'acceptation par le Conseil du renvoi à la Municipalité;
4. probabilité que la Municipalité suive l'esprit de la suggestion;
5. probabilité d'acceptation par le Conseil des conclusions du rapport municipal.

Pour chaque étape, fournir:
- un score indicatif (`Faible`, `Moyen`, `Bon`, `Très bon`);
- 3 risques bloquants max;
- contre-arguments probables;
- correctifs minimaux proposés (formulation, périmètre, charge, calendrier, coût).

## Inputs

- Texte du postulat (optionnel en phase 1, requis en phase 2).
- Contexte communal (problème, urgence, acteurs, historique).
- Sources locales disponibles (règlement du Conseil, bases cantonales, pratiques locales).
- Contraintes politiques connues (groupes, majorités probables, lignes rouges).

## Processus

1. Identifier la phase demandée (`demarrage`, `grill me`, ou les deux).
2. En phase `demarrage`, guider avec `assets/postulat_canevas.md` et combler les trous critiques.
3. Avant `grill me`, vérifier l'adéquation de l'instrument; en cas de doute, utiliser `orienter-initiative-communale`.
4. Evaluer le texte sous cinq portes de passage (Bureau, ODJ, Conseil-renvoi, Municipalité, Conseil-rapport).
5. Rendre une sortie actionnable avec priorités de correction et formulation de repli.

## Sortie attendue (format)

Réponse Markdown avec sections:
1. `Diagnostic express`
2. `Evaluation par etape`
3. `Points de blocage majeurs`
4. `Corrections minimales a fort impact`
5. `Version de repli strategique`
6. `Checklist pre-depot`

## Notes

- Le skill donne un appui procédural et politique, pas un avis juridique contraignant.
- Toujours expliciter les hypothèses quand les sources locales sont incomplètes.
- En cas d'incertitude forte, recommander une validation humaine (greffe, Bureau, juriste communal).
