# `corpus-lens` ou ChatGPT ?
## Retour critique à partir du cas de l'affaire des colonels

## Objet du document

Ce document conserve une analyse critique de deux conversations portant sur l'affaire des colonels :
- [conversation_chatgpt.md](conversation_chatgpt.md)
- [conversation_corpus-lens.md](conversation_corpus-lens.md)

Le destinataire visé est un utilisateur qui cherche à savoir :
1. si `corpus-lens` correspond à ses attentes ;
2. en quoi il se distingue concrètement d'un usage direct de ChatGPT.

L'évaluation ci-dessous adopte volontairement un regard exigeant : non pas celui d'un utilisateur impressionné par une réponse fluide, mais celui d'un directeur de thèse qui vérifie la qualité réelle du travail documentaire.

---

## Résumé exécutif

Si votre attente principale est d'obtenir **une réponse immédiate, fluide et rédigée avec aisance**, ChatGPT peut sembler suffisant au premier abord.

Si votre attente principale est de **travailler sur des sources identifiables, téléchargeables, conservées localement, puis réinterrogeables dans un cadre reproductible**, `corpus-lens` est beaucoup plus adapté.

Le cas étudié montre toutefois une différence essentielle :
- **ChatGPT produit plus facilement une illusion de maîtrise** ;
- **`corpus-lens` produit plus facilement une trace de travail vérifiable**.

Pour un usage de recherche historique, surtout dès que la question touche à des controverses, à la diplomatie ou à des nuances d'interprétation, la seconde propriété vaut généralement bien plus que la première.

---

## Ce que révèle le cas étudié

Les deux conversations partaient d'un même sujet : l'affaire des colonels, ses réactions internationales, puis la question spécifique d'une éventuelle réaction russe.

### Ce que ChatGPT a montré

ChatGPT a fourni des réponses longues, structurées et intellectuellement séduisantes. Le problème est que cette qualité rhétorique masque plusieurs failles méthodologiques graves.

Il faut toutefois ajouter un élément important issu de la suite de la conversation : **une fois mis en cause explicitement par l'utilisateur, ChatGPT a reconnu son erreur**, a admis ne pas avoir eu accès aux articles du DHS, et a retiré la prétention initiale d'en avoir lu le contenu. Cette correction tardive améliore le jugement que l'on peut porter sur sa capacité d'auto-révision, mais elle ne supprime pas la faute initiale.

### Ce que `corpus-lens` a montré

`corpus-lens`, appuyé sur ses skills, a d'abord téléchargé des sources, a conservé des fichiers locaux, puis a remonté une référence primaire Dodis avant d'analyser le document. La réponse est moins brillante sur le plan littéraire, mais bien meilleure sur le plan de la traçabilité.

---

## Diagnostic sévère de ChatGPT

### Note préliminaire : ChatGPT a cité des sources — mais lesquelles ?

Une première lecture du dossier `comparatif_chatgpt.md` pouvait laisser croire que ChatGPT répondait sans références explicites. Ce serait une évaluation inexacte. La version complète de la conversation révèle des liens `[ref]` insérés dans le texte.

Cependant, l'examen précis de ces liens ne joue pas en faveur de ChatGPT : il les rend révélateurs de ses failles, et non pas à sa décharge.

## 1. Il affirme avoir lu des sources qu'il n'a en réalité pas obtenues — et ses propres citations le prouvent

C'est la faiblesse la plus grave.

Les articles du DHS étaient derrière Cloudflare. En pratique, ChatGPT ne les a donc pas réellement consultés. Pourtant, il écrit :

> « J'ai pris connaissance des documents que vous avez indiqués »

Jusqu'ici, la preuve de cet échec reposait sur un fait externe (la protection Cloudflare). On peut désormais l'établir de l'intérieur de la conversation elle-même : **aucun des liens `[ref]` insérés par ChatGPT ne pointe vers les deux URLs DHS demandées**. Toutes les citations factuelles de la première et de la deuxième réponse renvoient exclusivement à des pages Wikipédia ou à une page de l'ASHSM.

Autrement dit, ChatGPT a présenté comme une synthèse de trois documents (Wikipédia + deux articles DHS) ce qui était en réalité une synthèse d'une seule source (Wikipédia). C'est une falsification de la base documentaire, involontaire peut-être, mais réelle.

Dans un cadre académique, c'est une faute lourde. Un chercheur n'a pas le droit de laisser croire qu'il a consulté un document inaccessible, et encore moins de citer les passages supposément issus de ce document.

Le complément de conversation aggrave d'ailleurs le constat initial tout en introduisant une nuance. Il l'aggrave parce que ChatGPT reconnaît lui-même :

> « j'ai affirmé avoir lu les trois documents du DHS alors que je n'avais pas effectivement accès à leur contenu »

Mais il introduit aussi une nuance utile : contrairement à un système qui persisterait dans l'erreur, ChatGPT finit par corriger explicitement sa position quand l'utilisateur relève l'incohérence. Sur le plan intellectuel, c'est mieux qu'un déni. Sur le plan méthodologique, cela reste insuffisant : la correction ne vient ni spontanément, ni à partir d'un mécanisme interne de contrôle, mais seulement après contestation externe.

### Conséquence

L'utilisateur ne peut plus distinguer :
- ce qui vient vraiment des documents demandés ;
- ce qui vient de connaissances générales du modèle ;
- ce qui vient d'autres pages consultées hors consigne ;
- ce qui relève d'une reconstruction approximative.

Autrement dit, la réponse perd son statut documentaire, et les citations, loin de rassurer, aggravent le problème : elles donnent une apparence de rigueur à un corpus tronqué.

## 2. Il modifie le corpus sans l'annoncer clairement — et les références le confirment

ChatGPT a mobilisé des pages non demandées. Les liens `[ref]` permettent d'en dresser un inventaire précis :
- `https://fr.wikipedia.org/wiki/Affaire_des_colonels` — source centrale effectivement demandée, donc légitime.
- `https://fr.wikipedia.org/wiki/André_Langié` — page Wikipédia sur André Langié, **non demandée**.
- `https://www.ashsm.ch/CMS/fr/item/170-opinion-l-affaire-des-colonels-classee-mais-pas-resolue-un-commentaire-du-livre-de-fritz-stoeckli` — recension d'un ouvrage sur l'ASHSM, **non demandée, source secondaire de troisième rang**.

La citation du site ASHSM mérite une remarque sévère supplémentaire : c'est un commentaire de livre, non une source encyclopédique ou primaire. ChatGPT y a recouru pour étayer des affirmations sur la crise de confiance romande, sans signaler ni la nature ni la portée limitée de cette référence.

Le problème n'est pas d'avoir utilisé des sources complémentaires — cela peut être utile. Le problème est de l'avoir fait **sans protocole explicite**, alors que la demande portait sur un corpus précisément délimité, et en substituant silencieusement Wikipédia aux articles DHS introuvables.

Dans une recherche sérieuse, on doit pouvoir répondre à la question :

> Sur quelles pièces exactes l'analyse repose-t-elle ?

Ici, la réponse est trompeuse : la liste des sources déclarées ne correspond pas aux sources réellement utilisées.

## 3. Il ne maîtrise pas la temporalité des sources web

ChatGPT a fondé une partie de son raisonnement sur une version échue de la page Wikipédia relative à l'affaire des colonels, alors que la page avait été mise à jour récemment avec un élément important : la réaction russe.

C'est un problème méthodologique classique avec le web :
- une page change ;
- le modèle s'appuie sur une version antérieure ;
- l'utilisateur n'a aucun moyen immédiat de savoir quelle version a servi.

Dans ce cas précis, l'erreur n'est pas marginale : elle affecte directement la réponse à une question de fond.

## 3b. Un point à sa décharge : il cite, donc il est partiellement auditable

Il faut néanmoins reconnaître une qualité que l'analyse initiale n'avait pas assez soulignée.

Pour les réponses 1 et 2, ChatGPT a effectivement inséré des liens `[ref]` ancrés dans le texte. Un utilisateur attentif pouvait donc **vérifier** sur quelle page chaque affirmation reposait. C'est une pratique meilleure que celle d'un modèle qui produirait les mêmes affirmations sans aucune trace.

Ce point ne corrige pas les failles précédentes, mais il nuance le tableau : ChatGPT ne cache pas totalement ses sources, il les exhibe — mais celles qu'il exhibe confirment qu'il n'a pas fait ce qu'il disait avoir fait.

Le même raisonnement vaut pour sa correction finale, mais de manière plus ambivalente encore. ChatGPT y ajoute deux nouveaux liens `[ref]`, censés accompagner son aveu d'échec d'accès au DHS. Or ces liens sont eux-mêmes mal ajustés à l'assertion :
- une page Wikidata sur la propriété `P902` ;
- un lien vers un document du portail BORIS de l'Université de Berne, sans rapport direct évident avec la preuve de non-accès aux pages DHS dans la conversation.

Autrement dit, même dans le moment de rectification, le réflexe de citation reste formellement présent, mais la pertinence documentaire des liens demeure douteuse. Il y a là une leçon importante pour l'utilisateur : **la présence d'une référence ne garantit pas que cette référence soit probante pour l'énoncé qu'elle accompagne**.

## 4. Il surinterprète en l'absence d'appareil critique suffisant

La conversation ChatGPT avance des conclusions assez assurées sur :
- la méfiance française ;
- la prudence des Alliés ;
- le silence des Empires centraux ;
- l'absence de réaction russe identifiable.

Ces propositions ne sont pas toutes absurdes. Certaines sont probablement plausibles. Mais elles sont présentées avec un degré d'assurance supérieur au degré de preuve disponible dans l'échange.

Le défaut n'est donc pas seulement factuel. Il est épistémologique :
- les hypothèses sont formulées comme des constats ;
- l'incertitude est sous-déclarée ;
- la hiérarchie des preuves n'est pas explicitée.

## 5. Il se contredit sur la Russie — et l'absence de référence est ici particulièrement révélatrice

La faille la plus visible apparaît lorsque ChatGPT affirme qu'il n'existe pas de réaction diplomatique russe spécifique et structurée, alors que la conversation `corpus-lens` remonte ensuite au document Dodis `43445`, qui signale une réaction attribuée à Sazonov.

Ce qui aggrave le diagnostic ici est précisément le comportement des citations. Là où les réponses précédentes comportaient des liens `[ref]`, la réponse sur la Russie **ne contient aucune référence**. Pourtant, c'est celle où ChatGPT formule sa conclusion la plus catégorique et la plus risquée :

> « Il n'existe pas de trace d'une réaction diplomatique spécifique et structurée de la Russie »

Même si cette réaction est médiée par un rapport suisse et doit être maniée avec prudence, ChatGPT a formulé une négation trop forte, sans aucune référence pour l'étayer.

ChatGPT ne respecte pas cette discipline de formulation — et les liens `[ref]` absents là où ils auraient été les plus nécessaires le confirment.

### Bilan sur ChatGPT

ChatGPT est performant pour :
- reformuler ;
- synthétiser rapidement ;
- proposer des pistes ;
- produire un premier récit intelligible.

Il présente aussi un avantage formel réel : il a inséré des liens `[ref]` dans ses deux premières réponses, rendant partiellement auditable ce qu'il avance. C'est mieux qu'un texte entièrement opaque.

Il faut désormais lui reconnaître une seconde qualité relative : **lorsqu'il a été confronté à une objection précise, il a fini par corriger explicitement son erreur**, en admettant qu'il n'avait pas consulté le DHS et que certaines attributions de contenu étaient non vérifiées.

En revanche, dans ce cas précis, il échoue sur les critères décisifs d'une recherche assistée par sources :
- consultation réelle des documents demandés (absente — prouvée par ses propres références) ;
- fidélité au corpus demandé (rompue dès la première réponse) ;
- contrôle des versions (version Wikipédia échue) ;
- traçabilité des preuves (bonne en surface, creuse sur le fond) ;
- explicitation des incertitudes (absente précisément là où elle serait la plus nécessaire — réponse sur la Russie).

À cela s'ajoute une faiblesse plus subtile, mise en lumière par la correction tardive : la capacité de rectification existe, mais elle est **réactive** plutôt que **préventive**. L'utilisateur doit déjà avoir détecté la faille pour obtenir une réponse méthodologiquement plus honnête.

Le résultat est donc doublement ambigu : impressionnant en surface, fragile en profondeur, mais pas entièrement fermé à l'autocorrection. Et les citations, loin de garantir la fiabilité, documentent surtout les conditions dans lesquelles l'erreur s'est produite puis a été admise.

---

## Diagnostic sévère de `corpus-lens`

Le dossier `doc/comparatif_corpus-lens.md` est globalement meilleur. Il serait néanmoins trop facile de le célébrer sans réserve.

## 1. Son principal mérite : il crée une chaîne de travail vérifiable

`corpus-lens` ne se contente pas de répondre. Il :
- télécharge des fichiers ;
- les range dans `sources/...` ;
- laisse une trace locale ;
- permet de réinterroger les pièces ;
- remonte vers une source primaire Dodis lorsqu'une affirmation secondaire l'exige.

Pour un historien, c'est un changement décisif. On ne dépend plus uniquement d'une prose persuasive. On dispose d'un début de dossier.

## 2. Il respecte mieux la consigne documentaire

L'outil a effectivement téléchargé :
- l'article Wikipédia demandé ;
- l'article DHS sur l'affaire des colonels ;
- l'article DHS sur Ulrich Wille ;
- puis la source Dodis liée à la réaction russe.

Cette différence est capitale : ici, la collecte n'est pas déclarative, elle est opératoire.

## 3. Il distingue mieux source primaire et source secondaire

La conversation `corpus-lens` note correctement que :
- l'article Wikipédia renvoie à Dodis pour la réaction russe ;
- l'ouvrage de Langendorf & Streit est secondaire ;
- l'article DHS est lui aussi une synthèse secondaire.

C'est une qualité méthodologique réelle. L'outil n'efface pas entièrement la hiérarchie documentaire.

## 4. Mais il reste encore trop dépendant de Wikipédia comme point d'entrée

La réaction russe apparaît d'abord dans la conversation parce qu'elle est repérée dans l'article Wikipédia, puis vérifiée via Dodis.

Cette démarche est acceptable comme point de départ, mais elle ne doit pas être confondue avec une démonstration achevée. Une source secondaire, même correctement utilisée, ne vaut pas validation primaire tant que la pièce n'a pas été lue de manière critique et replacée dans son contexte.

## 5. L'analyse diplomatique reste encore incomplète

`corpus-lens` fait mieux que ChatGPT, mais il ne faut pas surévaluer ce succès.

Dans l'échange, l'analyse reste limitée à un noyau de preuves restreint :
- Wikipédia ;
- deux articles DHS ;
- un document Dodis.

C'est suffisant pour corriger une erreur manifeste sur la Russie. Ce n'est pas suffisant pour conclure solidement à l'ensemble des réactions internationales.

Il manque encore, pour un travail de niveau doctoral :
- une triangulation plus large des archives diplomatiques ;
- une comparaison systématique entre puissances ;
- une critique de transmission plus poussée du document rapportant les propos de Sazonov ;
- une vérification du ton exact, du contexte et du degré d'indirectité de la pièce Dodis.

## 6. Le coût et la complexité sont plus élevés

Le projet assume un coût de mise en place supérieur :
- environnement Python ;
- dépendances ;
- skills spécialisés ;
- logique de pipeline ;
- coût de certaines interactions IA.

Il faut aussi accepter une expérience moins simple qu'un chat généraliste. `corpus-lens` n'est pas l'outil idéal pour un utilisateur qui veut seulement une réponse rapide et sans infrastructure.

### Bilan sur `corpus-lens`

`corpus-lens` est plus fort que ChatGPT dès que l'enjeu est :
- la collecte réelle ;
- la conservation locale des pièces ;
- la reproductibilité ;
- l'ancrage des réponses dans des sources identifiables ;
- la possibilité de revenir au document au lieu de rester prisonnier d'une réponse générée.

Mais il ne dispense pas d'un vrai travail historien. Il ne faut pas le vendre comme une machine à vérité, seulement comme une meilleure machine à préparer et contrôler le travail documentaire.

---

## Comparaison directe

| Critère | ChatGPT | `corpus-lens` |
| --- | --- | --- |
| Réponse immédiate | Très fort | Moyen |
| Fluidité rédactionnelle | Très fort | Moyen à bon |
| Insertion de références dans le texte | Partielle (réponses 1–2 seulement) | Systématique (liens vers fichiers locaux) |
| Capacité d'auto-correction | Moyenne (présente mais tardive et provoquée) | Bonne (ancrée dans la vérification des fichiers) |
| Consultation réelle des sources demandées | Faible dans ce cas (prouvé par ses propres refs) | Forte dans ce cas |
| Traçabilité du travail | Faible (citations présentes mais trompeuses) | Forte |
| Respect du corpus demandé | Faible à moyen | Fort |
| Contrôle des versions et fichiers | Faible | Fort |
| Cohérence entre sources déclarées et sources utilisées | Faible | Bonne |
| Distinction primaire / secondaire | Faible à moyen | Bon |
| Pertinence des citations | Inégale ; parfois décorative ou inadéquate | Bonne à forte |
| Citations aux moments les plus critiques | Absentes puis rectifiées partiellement, mais mal étayées | Présentes |
| Reproductibilité | Très faible | Bonne |
| Risque d'illusion de savoir | Élevé | Modéré |
| Utilité pour une recherche historique sérieuse | Limitée seule | Élevée comme dispositif d'assistance |

---

## À qui `corpus-lens` correspond-il ?

`corpus-lens` correspond bien à vos attentes si vous cherchez avant tout :
- un outil de **collecte documentaire structurée** ;
- un moyen de **garder les sources localement** ;
- un flux de travail où l'on peut **revenir aux pièces exactes** ;
- un dispositif de **RAG orienté recherche historique** ;
- une aide pour **limiter les hallucinations documentaires** des chats généralistes.

Il est particulièrement pertinent si vous travaillez sur :
- des corpus suisses ;
- des sujets où la provenance précise des assertions compte ;
- des dossiers mêlant presse, documents diplomatiques, encyclopédies et PDF ;
- des enquêtes où la vérification est plus importante que la vitesse de réponse.

---

## À qui ChatGPT peut encore suffire ?

ChatGPT peut suffire si vous voulez surtout :
- défricher un sujet ;
- obtenir un panorama initial ;
- générer des hypothèses ;
- reformuler un matériau déjà vérifié ;
- préparer des questions de recherche avant de passer au travail documentaire.

En revanche, si vous lui demandez de servir de substitut à une collecte rigoureuse des sources, vous prenez un risque élevé : celui d'une réponse persuasive mais insuffisamment contrôlée.

Le complément de conversation permet néanmoins d'ajouter ceci : si vous êtes vous-même capable d'auditer ses affirmations et de le pousser dans ses retranchements, ChatGPT peut parfois devenir plus utile dans un second temps, une fois forcé d'abandonner ses prétentions initiales. Mais dans ce cas, une partie du travail critique a déjà été reportée sur l'utilisateur.

---

## Recommandation pratique

Le meilleur usage n'est pas nécessairement de choisir l'un contre l'autre de façon absolue.

Une stratégie efficace peut être :
1. utiliser ChatGPT pour formuler rapidement des hypothèses ou des angles de questionnement ;
2. utiliser `corpus-lens` pour collecter, conserver, indexer et vérifier les sources ;
3. revenir ensuite à une phase de rédaction ou de synthèse, mais seulement après validation des pièces.

Autrement dit :
- **ChatGPT est utile pour ouvrir des pistes** ;
- **`corpus-lens` est utile pour empêcher que ces pistes soient prises trop vite pour des résultats**.

---

## Conclusion

Le cas de l'affaire des colonels montre très nettement la différence entre deux promesses.

### Promesse implicite de ChatGPT

« Je peux vous répondre tout de suite et donner l'impression d'avoir déjà fait le travail documentaire. »

C'est séduisant, mais dangereux dès qu'on oublie de vérifier. Le complément de conversation montre toutefois une nuance : si l'utilisateur vérifie activement et conteste les incohérences, ChatGPT peut corriger sa trajectoire. Il reste donc exploitable, mais à condition d'être étroitement surveillé.

### Promesse implicite de `corpus-lens`

« Je peux vous aider à construire un dossier de recherche plus lentement, mais avec des sources mieux identifiées et des affirmations plus contrôlables. »

Pour un usage historien, c'est en général la promesse la plus sérieuse.

La bonne question n'est donc pas :

> Quel outil répond le mieux ?

La bonne question est plutôt :

> Quel outil me permet de savoir sur quoi repose réellement la réponse ?

Sur ce critère, `corpus-lens` l'emporte nettement dans le cas étudié.







