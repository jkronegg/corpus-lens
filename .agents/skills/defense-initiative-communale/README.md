# Skill: defense-initiative-communale

## Accès rapide

**Objectif principal**: Préparer un conseiller communal à défendre son initiative face au Conseil communal, via une simulation réaliste (pitch + grill-me + debriefing).

---

## Flux d'utilisation

### 1. Avant le grill-me : Diagnostic rapide
👉 Consultez `assets/diagnostic_rapide.md` pour évaluer rapidement la solidité de l'initiative (5 minutes).

- Si score < 18: travail préalable requis (collecte de données, contacts).
- Si score ≥ 18: procédez au grill-me.

---

### 2. Pendant le grill-me : Questions d'attaque
👉 Consultez `assets/grille_questions_attaque.md` pour poser des questions progressives (bien-fondé → faisabilité → coûts/bénéfice → politique).

- Poser 10-15 questions.
- Enregistrer les réponses.
- Scorer chaque réponse (1-4).
- Adapter les questions suivantes en fonction des réponses.

---

### 3. Après le grill-me : Debriefing et plans d'action
👉 Utilisez `assets/template_debriefing.md` pour structurer votre feedback.

- Résumer les points forts et faibles.
- Proposer 3 ajustements textuels prioritaires.
- Documenter les données manquantes.
- Créer les fiches de réplique rapide (voir point 4).

---

### 4. Préparation aux objections : Fiches de réplique
👉 Consultez `assets/template_fiches_replicques.md` pour préparer des ripostes courtes (30-60 sec) aux objections probables.

- Une objection = une réplique (courte et sourcée).
- Préparer les 4-5 objections les plus probables.

---

### 5. Exemple complet
👉 Lisez `assets/exemple_complet_defenseinitiative.md` pour voir comment tous ces éléments s'assemblent dans un cas réel.

- Diagnostic rapide appliqué à une initiative.
- Grill-me simulé avec 13 questions.
- Debriefing détaillé.
- Fiches de réplique et checklist pré-séance.

---

## Structure du skill

```
defense-initiative-communale/
├── SKILL.md                                 [← Vous êtes ici]
├── README.md                                [← Ce fichier]
└── assets/
    ├── diagnostic_rapide.md                 [Évaluation rapide (5 min)]
    ├── grille_questions_attaque.md          [18 questions d'attaque variées]
    ├── template_fiches_replicques.md        [Template pour les répliques courtes]
    ├── template_debriefing.md               [Template complet de debriefing]
    └── exemple_complet_defenseinitiative.md [Cas pratique détaillé]
```

---

## Qui utilise ce skill ?

- **Conseiller communal**: Préparer sa défense avant séance plénière.
- **Groupe politique**: Stress-test ses initiatives avant présentation.
- **Collaborateur politique**: Préparer un conseiller (via grill-me simulé).

---

## En 30 secondes

| Phase | Durée | Input | Output |
|---|---|---|---|
| **Diagnostic rapide** | 5 min | Initiative (texte) | Score 1-36 + priorités |
| **Grill-me** | 20-30 min | Initiative + conseiller | Réponses enregistrées + scores |
| **Debriefing** | 30 min | Réponses + analyse | Rapport Markdown + plans d'action |
| **Fiches de réplique** | 15 min | Objections probables | 4-5 fiches de riposte rapide |
| **Checklist pré-séance** | 10 min | Tous les éléments ci-dessus | Liste de vérification + timing |

---

## Notes importantes

✅ **Ce skill simule** un débat réaliste dans un contexte de Conseil communal.

❌ **Ce skill ne remplace PAS**:
- Une validation juridique officielle auprès du Bureau du Conseil.
- La rédaction complète d'une initiative (utiliser `aide-redaction-postulat`).
- Le choix de l'instrument (utiliser d'abord `orienter-initiative-communale`).

---

## Lien vers le SKILL.md complet

👉 `SKILL.md` contient:
- Objectifs détaillés.
- Descriptions des 3 phases (Pitch, Grill-me, Debriefing).
- Quand utiliser / ne pas utiliser.
- Inputs et processus complets.
- Grille de notation et catégories de questions.
- Sortie attendue (format Markdown).

Consulter ce fichier pour la logique complète du skill.

---

## Exemples de résultats attendus

### Après Diagnostic rapide
```
Score: 18/36 (Moyen)
Verdict: Grill-me requis. 2-3 corrections avant séance.
Priorités:
  1. Contacter TL pour confirmer faisabilité.
  2. Budgétiser précisément (estimation TL).
  3. Identifier 2-3 alliés au Conseil.
```

### Après Debriefing
```
## Points forts
- Argumentation justice sociale bien structurée.
- Ouverture à la critique (auto-correction Q17).

## Points d'amélioration
- Aucun contact préalable avec TL (critique).
- Budget plucké du néant (CHF 50'000?).
- Zéro ancrage citoyen externe.

## Top 3 actions avant séance
1. Contacter TL (24h).
2. Documenter benchmarks externes (3 jours).
3. Rencontre Municipalité (2 jours).
```

### Fiches de réplique
```
### Objection: "C'est trop coûteux pour peu de bénéficiaires"

**Réplique rapide:**
"Trois points: (1) Surcoût CHF 120k/an = 0,8% du budget. (2) Justice sociale: 150-200 ménages sans voiture. (3) [Commune A] l'a fait en 2019, augmentation 35% d'usagers."

**Variante:**
"Si TL dit non, on saura pourquoi. Mieux vaut l'essayer."
```

---

## Questions fréquentes

**Q: Comment structurer le grill-me?**
→ Utiliser `grille_questions_attaque.md`. Poser progressivement: bien-fondé (Q1-3), faisabilité (Q4-8), coûts (Q9-13), politique (Q14-18). Adapter selon le contexte.

**Q: Combien de questions poser?**
→ 10-15 en fonction de la complexité. Pas besoin de toutes les 18.

**Q: Comment scorer les réponses?**
→ Voir `template_debriefing.md`, tableau "Analyse des réponses". Critères: pertinence, solidité, clarté, ouverture.

**Q: Que faire si l'initiative est très faible?**
→ Diagnostic rapide le montre (score < 12). Recommander un délai de 2-3 semaines pour amélioration, pas dépôt immédiat.

**Q: Comment préparer les objections?**
→ Identifier les 4-5 objections les plus probables (regarder le groupe politique opposant, les lignes rouges du Conseil). Pour chaque: formulation rapide + source. Voir `template_fiches_replicques.md`.

---

## Ressources connexes

- `aide-redaction-postulat`: Si l'initiative n'est pas encore rédigée.
- `orienter-initiative-communale`: Si doute sur le bon instrument (postulat, motion, question, etc.).
- Règlement du Conseil communal de votre commune (pour recevabilité formelle).

---

## Version et historique

- **v1.0** (2026-09-27): Création initiale du skill avec 3 phases (pitch, grill-me, debriefing), grille de questions d'attaque, templates et exemple complet.

---

## Auteur et support

Pour questions ou amélioration du skill, contacter [votre structure de support].

