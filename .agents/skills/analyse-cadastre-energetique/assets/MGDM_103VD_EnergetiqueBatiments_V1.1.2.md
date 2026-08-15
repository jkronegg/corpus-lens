---
titre: "MGDM 103VD EnergetiqueBatiments V1.1.2"
source: "initiatives/world_model_mazout/MGDM_103VD_EnergetiqueBatiments_V1.1.2.pdf"
source_signature: "a217a1293ee054e69f672acf13751a00"
date_publication: "23.07.2025"
date_event: "22.05.2025"
date_extraction: "2026-08-13T22:12:56.686965"
pages: "36"
ocr_pages: "36"
ocr_quality: "1.000"
transformation_by: "skill convert-pdf-to-md"
language_distribution: "fr:97, en:3"
author: "skill convert-pdf-to-md"
---
Pages détectées: 1-36

## Page 1

cavend

Direction du Cadastre et de la Géoinformation

SYSTEME DE MANAGEMENT DE LA QUALITE
GEODONNEES
Modèles de géodonnées minimaux

# Modèle de géodonnées minimal

## Cadastre énergétique des bâtiments vaudois

Documentation sur les modèles

Modèle appliqué à la géodonnée de base relevant du droit cantonal n° :

- 103 – VD (Cadastre énergétique des bâtiments vaudois)

Equipe du projet : Lois Poix daude, Michael Weber

Chef de l'équipe du projet : Victor Braune

Modélisateur : Lois Poix Daude

Service spécialisé : Direction de l'Energie (DGE/DIREN)

Version : 1.1.2

Adopté le : 22.05.2025

## Page 2

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|  Version du 15.05.2024 | Validation | Distribution | Classement  |
| --- | --- | --- | --- |
|  Remplace version du 20.11.2023 |  | Interne/externe | 7401  |

## Suivi des modifications

|  Version | Description | Date  |
| --- | --- | --- |
|  0.1 | Amorce du modèle | 11.04.23  |
|  0.2 | Correction UDI | 28.06.23  |
|  1.0 | Validation UDI | 25.07.23  |
|  1.1 | Suppression des variables STRNAME,DEINR, DPLZ4, DPLZNAME | 17.10.23  |
|  1.2 | Adaptation UML classe de relation ID_EMPREINTE | 16.11.23  |
|  1.3 | Inscription des métadonnées | 01.02.24  |
|  1.4 | Révision terminologie | 14.02.24  |
|  1.5 | Domaines de valeurs | 04.03.24  |
|  1.6 | Modèle de livraison – correctifs appliqués | 15.05.24  |
|  1.7 | Révision de la symbologie Ajout de l'attribut sur RegenerGeo *NBRE_EGID* | 18.07.24  |
|  1.8 | Révision interlis + inclusion uml | 15.08.24  |
|  1.9 | Changement type ETAT_REGENER (str -> date) | 19.08.24  |
|  1.9.3 | Suppression représentation TYPE_EMPREINTE, calage tolérance, renommage variable « rénovation » | 17.02.25  |
|  1.10 | Ajout CONSO_GWAERH1, H2, W1, W2 |   |

2 / 36

7401

## Page 3

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|   | Modification format GBAUJ, RENOV _LOURDE_ANNEE, RE- NOV_LEGERE_ANNEE sur RegEnerGeo (Date -> Numérique entier court) Modification SRCE_EMPREINTE sur RegEnerGeo (Texte -> nu- mérique entier court |   |
| --- | --- | --- |

3 / 36

7401

## Page 4

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

# Table des matières

|  **1** | **Introduction** | **5**  |
| --- | --- | --- |
|  1.1 | Contexte | 5  |
|  1.2 | Objectif du document | 5  |
|  1.3 | Provenance des données, publication de l'information et niveau d'accès | 5  |
|  **2** | **Bases pour la modélisation** | **6**  |
|  2.1 | Normes existantes et valeur juridique | 6  |
|  2.2 | Bases légales des géodonnées de base | 6  |
|  **3** | **Description du modèle** | **6**  |
|  3.1 | Sémantique du modèle | 7  |
|  3.2 | Modèle de représentation | 8  |
|  3.2.1 | Exemple de représentation | 8  |
|  3.2.2 | Détails du modèle de représentation | 9  |
|  **4** | **Structure du modèle** | **10**  |
|  4.1 | Modèle de données conceptuel | 14  |
|  4.2 | Diagramme de classes UML | 14  |
|  4.3 | Catalogue des objets | 17  |
|  4.3.1 | Registre énergétique des bâtiments vaudois (regener) | 17  |
|  4.3.2 | Cadastre énergétique des bâtiments vaudois (RegEnerGeo) | 20  |
|  **5** | **Annexe** | **20**  |
|  5.1 | A – Glossaire | 26  |
|  5.2 | B – Glossaire technique | 26  |
|  5.3 | C – Fichier modèle INTERLIS MN95 | 27  |

4 / 36

7401

## Page 5

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

# 1 Introduction

## 1.1 Contexte

La Suisse s'est dotée en 2007 d'un nouveau droit fédéral de la géoinformation par le biais de la Loi fédérale sur la géoinformation (*LGéo ; RS 510.62*). Elle est entrée en vigueur le 1$^{er}$ juillet 2008, en même temps que la plupart de ses ordonnances d'exécution comme l'Ordonnance sur la géoinformation (*OGéo ; RS 510.620*), l'Ordonnance sur les noms géographiques (*ONGéo ; RS 510.625*) ou encore l'Ordonnance sur la mensuration officielle (*OMO ; RS 211.432.2*).

Dans ce contexte, les cantons doivent adapter leur législation aux exigences du droit fédéral. Pour ce faire, le canton a établi une loi (*LGéo-VD ; RSV 510.62*), ainsi qu'un règlement d'application de cette loi (*RLGéo-VD ; RSV 510.62.1*). Elle a pour objectif de définir des normes contraignantes pour le relevé et la modélisation de géodonnées, ainsi que de faciliter l'accès et l'échange de géodonnées, en particulier des géodonnées de base relevant du droit cantonal. Cette loi et son règlement ont été adoptés en 2012 et l'entrée en vigueur a été fixée au 1$^{er}$ janvier 2013. Ils constituent la base légale pour la gestion des géodonnées du canton et des communes.

Par ailleurs, la *LGéo-VD* permet une utilisation multiple des mêmes données dans les applications les plus diverses. Ainsi, le *RLGéo-VD* fixe l'établissement d'un modèle minimal de géodonnées afin de permettre l'harmonisation des échanges entre partenaires en facilitant les relations entre les différentes bases de données. L'accès aux données collectées est géré par d'importants moyens et s'en trouve amélioré pour les autorités et les institutions, les milieux économiques et la population, permettant, entre autres, des développements applicatifs robustes et innovants.

## 1.2 Objectif du document

Le modèle de géodonnées minimal présenté dans ce document décrit les géodonnées de base relevant du droit cantonal, relatives au cadastre énergétique des bâtiments vaudois. Ces géodonnées s'inscrivent dans la nécessité de fournir au public un moyen d'accéder aux informations énergétiques des bâtiments pour toute l'étendue géographique du canton de Vaud.

Le modèle de géodonnées minimal décrit ci-après permet de garantir que le service spécialisé, ou son gestionnaire la direction de l'énergie (ci-après DIREN), est à même de gérer les données dans cette forme et puisse les mettre à disposition des partenaires avec les relations définies dans ce même modèle de données.

Ce modèle sert à structurer l'échange de ces données entre différents partenaires mais il ne reflète qu'en partie le modèle d'acquisition des données, tout comme c'est le cas également pour le modèle de gestion métier relatif à ces données.

## 1.3 Provenance des données, publication de l'information et niveau d'accès

Les géodonnées utilisées pour concevoir le modèle minimal sont propriétés de la Direction de l'énergie. Elles sont composées de deux classes d'entités sur lesquelles nous allons revenir : la table recensant les informations énergétiques à l'EGID, et la géodonnée agrégeant ces informations à l'échelle du bâtiment selon son empreinte au sol (tel qu'on le voit « à l'œil nu »).

Ces données et géodonnées sont accessibles au public : en effet, selon l'annexe 2 de la *RLGéo*, ces géodonnées sont classées au niveau d'autorisation d'accès A, c'est-à-dire qu'elles sont accessibles au public et qu'un service de téléchargement est prévu à cet effet. Ceci s'applique également aux entités représentant des infrastructures de propriété privée.

5 / 36

7401

## Page 6

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Elles sont également mises en ligne sur les géoportails www.geo.vd.ch et www.pdcn.vd.ch/ .

## 2 Bases pour la modélisation

### 2.1 Normes existantes et valeur juridique

Les normes existantes se réfèrent aux bases légales mentionnées ci-après et s'insèrent principalement dans le cadre de la planification énergétique territoire et l'aide à la décision en matière d'aménagement et urbanisme. La définition des contenus du modèle a tenu compte des recommandations fédérales de l'Organe de coordination de la géoinformation (COSIG) pour l'harmonisation des géodonnées de base. La mise en œuvre technique et formelle des catalogues d'objets et du modèle de données conceptuel suit les mêmes directives.

Le modèle de géodonnées minimal présenté décrit le noyau commun d'un jeu de données relatif au cadastre énergétique des bâtiments vaudois sur lequel peuvent se greffer des modèles de géodonnées élargis, de niveau cantonal ou communal, afin d'illustrer les différents besoins d'utilisation.

Le modèle de géodonnées minimal prescrit ici oblige l'Office cantonal à mettre à disposition les données sous cette forme pour faciliter leur échange entre les différents partenaires et services. La Directive cantonale (7402) sur les MGDM pour la mise en œuvre de la LGéo-VD établie par la DGTL-DCG sert aussi de référence pour l'élaboration des modèles de géodonnées minimaux.

### 2.2 Bases légales des géodonnées de base

Il n'existe lors de l'écriture de ce modèle pas de bases légales en place permettant de justifier juridiquement la mise en place du cadastre énergétique des bâtiments vaudois, comme il en est pour les cadastres mentionnés dans l'article 20 de la LVLene : Cadastres et données énergétiques. La publication de ce cadastre est soutenue par son inscription dans l'annexe 2 de la RLGéo ainsi que les besoins croissants des communes d'accéder aux informations énergétiques de leur parc bâti. Toutefois le canton de Vaud prévoit d'inscrire ces éléments dans une base légale qui figurera dans la nouvelle loi vaudoise sur l'énergie (LVLEne), dont la révision complète est en cours.

Toutefois, la publication du cadastre énergétique des bâtiments vaudois est soutenue par le titre 2bis de la LVLEne traitant sur la planification énergétique, et la nécessité d'offrir aux communes et autres acteurs territoriaux les outils et données leur permettant de mener à bien leur planification et leur transition énergétique.

## 3 Description du modèle

Ce modèle de géodonnées minimal est régi selon deux classes d'entités et une classe de relation, mettant en lien ces deux entités :

- La première classe d'entités – ci-après RegEner - est une table de données documentant les informations structurelles des bâtiments (âge, rénovation, catégorie d'usage, etc.) et énergétiques (besoins de chaleur, consommation thermique, type de chaudière et de chauffage, etc.).
- La seconde classe – ci-après RegEnerGeo - concerne les entités géospatialisées de géométrie polygonale, correspondant aux bâtiments cadastrés du canton par la mensuration officielle (MO).

Une dernière table est annexée au modèle et contient les métadonnées propres aux dates d'extraction des différentes bases de données utilisées dans la modélisation du RegEner.

6 / 36

7401

## Page 7

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

![img-0.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-0.jpeg)

Figure 1 – Vue d'ensemble méthodologie

### 3.1 Sémantique du modèle

Concernant le **RegEner**, de nombreuses variables sont volontairement similaires à celles qu'on trouve dans le Registre des bâtiments et logements : le **RegEner** est aligné sur le registre des bâtiments et logements RegBL - modèle uniforme pour tous les cantons – auquel les données énergétiques sont greffées par la DIREN : estimations des **besoins de chaleur**, des **consommations**, des **émissions de CO2**, etc. Ainsi, chaque variable déjà présente dans le RegBL est reprise avec le même nom (par exemple GEBF pour la surface de référence énergétique) alors qu'une variable créée par la DGE-DIREN sera nommée de manière francophone (p.ex. BESOINS_CH pour les besoins de chaleur). La précision du **RegEner** est de l'ordre de l'EGID, l'identifiant fédéral du bâtiment.

Le **RegEnerGeo** constitue l'extension géographique du **RegEner**. Les géométadonnées donnent les informations du **RegEner** dans un format simplifié et cartographiable, notamment les variables relatives aux informations structurelles du bâtiment.

La classe de relation permet de lier la table de données **RegEner** avec la géodonnée **RegEnerGeo**, afin d'obtenir les informations du **RegEner** en cas d'interrogation de la classe d'entités **RegEnerGeo**. Un identifiant unique par bâtiment cadastré sert de clé primaire pour la jointure des deux classes.

7 / 36

7401

## Page 8

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

La table recensant les informations sur les métadonnées est indépendante de deux classes d'entités RegEner et RegEnerGeo et ne présente aucune relation avec celles-ci.

Les attributs des deux classes d'entités et de la table propre aux métadonnées sont précisés dans le chapitre 4.3, Catalogue des objets.

## 3.2 Modèle de représentation

Le modèle de représentation reprend le code couleur hexadécimal préconisé par Swisstopo sur le cadastre des énergies de la confédération afin d'assurer la cohérence entre le cadastre énergétique fédéral et le celui du canton de Vaud et ne pas rendre l'utilisateur confus en cas de comparaison des deux plateformes de visualisation des géodonnées.

### 3.2.1 Exemple de représentation

![img-1.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-1.jpeg)

Figure 2. Modèle de représentation du cadastre énergétique des bâtiments vaudois

8 / 36

7401

## Page 9

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

### 3.2.2 Détails du modèle de représentation

#### 3.2.2.1 Agent énergétique principal pour le chauffage

![img-2.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-2.jpeg)

Figure 3 - Exemple de représentation - Agent énergétique principal pour le chauffage

|  Représentation | Champs de valeur | Valeur « Rouge » | Valeur « Vert » | Valeur « Bleu » | Contour du trait / caractéristique  |
| --- | --- | --- | --- | --- | --- |
|   | AE_H : « Au-cun » | 225 | 225 | 225 | Aucun  |
|   | AE_H : « In-déterminé » | 25 | 25 | 147 | Trait plein Ép. 0.40 RGB : 25/25/147  |
|   |   |  210 | 210 | 210 | Symbole ligne de ha-chure RGB : 210/210/210 Ép. 3  |
|   |   |  25 | 25 | 147 | Symbole des lignes de hachure RGB : 25/25/147 Ép. 0.4  |
|   | AE_H : « Bois » | 65 | 243 | 89 | Aucun  |
|   | AE_H : « CAD » | 227 | 125 | 255 | Aucun  |
|   | AE_H : « Electricité (PAC) » | 114 | 224 | 255 | Aucun  |
|   | AE_H : « Electricité » | 255 | 255 | 0 | Aucun  |

9 / 36

7401

## Page 10

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|   | AE_H : « Gaz » | 95 | 95 | 95 | Aucun  |
| --- | --- | --- | --- | --- | --- |
|   | AE_H : « Ma-zout » | 0 | 0 | 0 | Aucun  |
|   | AE_H : « So-laire ther-mique » | 253 | 192 | 46 | Aucun  |

##### 3.2.2.2 Emission directes de CO2 estimées (kgCO2/an) – chauffage et eau chaude sanitaire (ECS)

|  Représentation | Champs de valeur | Valeur « Rouge » | Valeur « Vert » | Valeur « Bleu » | Contour du trait / caractéristique  |
| --- | --- | --- | --- | --- | --- |
|   | CO2_DIR == 0 | 225 | 225 | 225 | Aucun  |
|   | CO2_DIR > 0 AND < 15'000 | 129 | 192 | 235 | Aucun  |
|   | CO2_DIR > 15'000.1 AND < 50'000 | 70 | 149 | 227 | Aucun  |
|   | CO2_DIR > 50'000.1 AND < 100'000 | 33 | 107 | 209 | Aucun  |
|   | CO2_DIR > 100'000.1 AND < 200'000 | 28 | 58 | 176 | Aucun  |
|   | CO2_DIR > 200'000 | 8 | 8 | 117 | Aucun  |

##### 3.2.2.3 Emission directes estimées de CO2 – chauffage et ECS (kgCO2/m²/an)

|  Représentation | Champs de valeur | Valeur « Rouge » | Valeur « Vert » | Valeur « Bleu » | Contour du trait / caractéristique  |
| --- | --- | --- | --- | --- | --- |
|   | (CO2_DIR/G EBF) < 5'000 | 255 | 247 | 251 | Aucun  |
|   | (CO2_DIR/G EBF) > 5'000 AND < 15'000 | 219 | 216 | 234 | Aucun  |
|   | (CO2_DIR/G EBF) > | 153 | 185 | 217 | Aucun  |

10 / 36

7401

## Page 11

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|   | 15'000.1AND <30'000 |  |  |  |   |
| --- | --- | --- | --- | --- | --- |
|  ![img-3.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-3.jpeg) | (CO2_DIR/GEBF) >30'000.1AND <60'000 | 33 | 107 | 209 | Aucun  |
|  ![img-4.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-4.jpeg) | (CO2_DIR/GEBF) >60'000.1AND <100'000 | 1 | 70 | 54 | Aucun  |
|  ![img-5.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-5.jpeg) | (CO2_DIR/GEBF) >100'000 | 8 | 8 | 117 | Aucun  |

##### 3.2.2.4 Besoins estimés (MWh/an) – chauffage et eau chaude sanitaire (ECS)

![img-6.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-6.jpeg)

Figure 4 - Exemple de représentation - Besoins estimés (MWh/an) - chauffage et eau chaude sanitaire (ECS)

|  Représentation | Champs de valeur | Valeur « Rouge » | Valeur « Vert » | Valeur « Bleu » | Contour du trait / caractéristique  |
| --- | --- | --- | --- | --- | --- |
|  ![img-7.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-7.jpeg) | BE-SOINS_TOT < 50'000 | 245 | 245 | 0 | Aucun  |
|  ![img-8.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-8.jpeg) | BE-SOINS_TOT | 245 | 184 | 0 | Aucun  |

11 / 36

7401

## Page 12

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|   | >50'000.1AND <100'000 |  |  |  |   |
| --- | --- | --- | --- | --- | --- |
|  ![img-9.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-9.jpeg) | BE-SOINS_TOT>100'000.1AND <300'000 | 245 | 122 | 0 | Aucun  |
|  ![img-10.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-10.jpeg) | BE-SOINS_TOT>300'000.1AND <750'000 | 245 | 61 | 0 | Aucun  |
|  ![img-11.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-11.jpeg) | BE-SOINS_TOT>750'000 | 245 | 0 | 0 | Aucun  |

##### 3.2.2.5 Besoins estimés (MWh/m²/an) – chauffage et eau chaude sanitaire (ECS)

![img-12.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-12.jpeg)

Figure 5 - Exemple de représentation - Besoins estimés (MWh/m²/an) - chauffage et eau chaude sanitaire (ECS)

|  Représentation | Champs de valeur | Valeur « Rouge » | Valeur « Vert » | Valeur « Bleu » | Contour du trait / caractéristique  |
| --- | --- | --- | --- | --- | --- |
|  ![img-13.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-13.jpeg) | (BE-SOINS_TOT/GEBF) < 50 | 255 | 245 | 240 | Aucun  |
|  ![img-14.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-14.jpeg) | (BE-SOINS_TOT/ | 252 | 187 | 161 | Aucun  |

12 / 36

7401

## Page 13

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|   | GEBF) > 50 AND < 100 |  |  |  |   |
| --- | --- | --- | --- | --- | --- |
|   | (BE- SOINS_TOT/ GEBF) > 100.1 AND < 125 | 203 | 24 | 29 | Aucun  |
|   | (BE- SOINS_TOT/ GEBF) > 125.1 AND < 150 | 158 | 24 | 29 | Aucun  |
|   | (BE- SOINS_TOT/ GEBF) > 150 | 103 | 0 | 13 | Aucun  |

13 / 36

7401

## Page 14

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

# 4 Structure du modèle

# 4.1 Modèle de données conceptuel

La structure du modèle minimal gravite autour de la classe RegEner. La classe d'entités RegEner-Geo correspond aux bâtiments cadastrés du canton, héritant des informations énergétiques et structurelles données par le RegEner par la classe de relation de type Composition : si un individu du RegEner disparait (par ex. destruction du bâtiment), alors il ne sera pas cadastré via le RegEnerGeo. La cardinalité de cette classe de relation est de type 1-n : un bâtiment au sens RegEnerGeo (bâtiment à l'œil nu) peut contenir 1 à n individu(s) issu(s) du RegEner (bâtiment au sens de l'EGID).

Dans ce cas, les variables et informations délivrées par la classe d'entité RegEnerGeo dépendent également du RegEner car, méthodologiquement, elles proviennent d'agrégations statistiques des données fournies par la classe RegEner.

Si un seul individu RegEner est contenu dans un bâtiment RegEnerGeo, alors les informations sont données telles quelles.

La table MetaDataBat est indépendante des deux classes d'entités RegEnerGeo et RegEner.

# 4.2 Diagramme de classes UML

La Confédération a établi un template uml disposant de modules de base pour la modélisation. Une partie de ceux-ci a été utilisée pour l'élaboration du diagramme de classe ci-dessous.¹, notamment pour la géométrie des classes.

La majorité des domaines de valeurs consistent en la traduction des codes fournis par le RegEner en description textuelle. La plupart de ces codes proviennent de la documentation officielle relative au RegBL, normes SIA et codes propres à la méthodologie élaborée par la DGE-DIREN.

¹ http://www.geo.admin.ch/internet/geoportal/fr/home/topics/geobasedata/models.html

14 / 36

7401

## Page 15

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

![img-15.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-15.jpeg)

![img-16.jpeg](MGDM_103VD_EnergetiqueBatiments_V1.1.2_ocr_images/img-16.jpeg)

7401

## Page 16

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

**Figure 6. Diagramme de classes UML du cadastre énergétique des bâtiments vaudois**

16 / 36

7401

## Page 17

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

### 4.3 Catalogue des objets

Le catalogue des objets situé ci-dessous a été directement élaboré à partir du logiciel *UML Editor* afin de respecter les recommandations structurales pour l'élaboration des modèles de géodonnées minimaux de la Confédération.

#### 4.3.1 Registre énergétique des bâtiments vaudois (RegEner)

|  Nom | Cardinalité | Type | Description  |
| --- | --- | --- | --- |
|  EGID | 1 | 0..999999999 | Identifiant fédéral du bâtiment  |
|  COORD_X | 1 | 2490000..2590000 | Coordonnée Est de l'EGID  |
|  COORD_Y | 0..1 | 1110000..1210000 | Coordonnée Nord de l'EGID  |
|  GGDENR | 1 | 5400..6000 | Numéro de la commune selon l'Office Fédéral de la statistique  |
|  GGDENAME | 1 | TEXTE | Nom de la commune  |
|  ALTI_BAT | 0..1 | 300..4000 | Altitude du bâtiment au rez-de-chaussée  |
|  GKAT | 0..1 | GKAT | Catégorie du bâtiment, selon le RegBL  |
|  GKLAS | 0..1 | GKLAS | Classe du bâtiment, selon le RegBL  |
|  AFF_SIA_1 | 0..1 | AFF_SIA | Affectation SIA principale  |
|  AFF_SIA_2 | 0..1 | AFF_SIA | Affectation SIA secondaire  |
|  AFF_SIA_PROV | 0..1 | TEXTE | Provenance de l'information - AFF_SIA(1/2)  |
|  GEBF | 0..1 | 0.0..999999999.9 | Surface de référence énergétique totale  |
|  GEBF_PROV | 0..1 | TEXTE | Provenance de l'information - GEBF  |
|  GEBF_PART | 0..1 | 0.000..1.000 | Part en pourcent de la SRE associée à AFF_SIA_1  |
|  GEBF_PART_PROV | 0..1 | TEXTE | Source utilisée pour procéder à la répartition de GEBF par affectation  |
|  GAREA_CORR | 0..1 | 0.0..999999.9 | Surface corrigée de l'EGID en mètre carrés (unité similaire à la surface RegBL)  |
|  GASTW | 0..1 | 0..30 | Nombre d'étages  |
|  GBAUJ | 0..1 |  | Année de construction de l'EGID  |
|  ENER_EPOQUE | 0..1 | ENER_EPOQUE | Epoque énergétique de référence pour le calcul des besoins de chaleur du bâtiment. Si une rénovation lourde est renseignée c'est l'époque de rénovation lourde, sinon l'époque de construction  |
|  RENOV_LOURDE_DATE | 0..1 |  | Date de dernière rénovation lourde de l'EGID  |
|  RENOV_LOURDE_DATE_DATE | 0..1 |  | Date de renseignement de l'information RENOV_LOURDE_DATE  |

17 / 36

7401

## Page 18

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|  RENOV_LEGERE_DATE | 0..1 |  | Date de dernière rénovation légère de l'EGID  |
| --- | --- | --- | --- |
|  RENOV_LEGERE_DATE_DATE | 0..1 |  | Date de renseignement de l'information RENOV_LEGERE_DATE  |
|  RENOV_LOURDE_PROV | 0..1 | TEXTE | Provenance de l'information RENOV_LOURDE_DATE  |
|  RENOV_LEGERE_PROV | 0..1 | TEXTE | Provenance de l'information RENOV_LEGERE_DATE  |
|  GWAERZH1 | 0..1 | GWAERZH | Système de production de chauffage principal  |
|  GWAERZH1_PART | 0..1 | 0.000..1.000 | Part couverte par le système de chauffage principal GWAERZH1  |
|  GWAERDATH1 | 0..1 |  | Date de renseignement de l'information GWAERZH1  |
|  GWAERZH2 | 0..1 | GWAERZH | Système de production de chauffage secondaire (si existant)  |
|  GWAERZDATH2 | 0..1 |  | Date de renseignement de l'information GWAERZH2  |
|  GWAERZW1 | 0..1 | GWAERZW | Système de production de chauffage principal dédié à l'ECS  |
|  GWAERZW1_PART | 0..1 | 0.000..1.000 | Part couverte par le système de chauffage principal dédié à l'ECS GWAERZW1  |
|  GWAERDATW1 | 0..1 |  | Date de renseignement de l'information GWAERZW1  |
|  GWAERZW2 | 0..1 | GWAERZW | Système de production de chauffage secondaire dédié à l'ECS (si existant)  |
|  GWAERDATW2 | 0..1 |  | Date de renseignement de l'information GWAERZW2  |
|  GENH1 | 0..1 | GEN | Source d'énergie pour le système de production GWAERZH1 correspondant  |
|  GWAERSCEH1 | 0..1 | TEXTE | Provenance de la source d'information pour GENH1  |
|  GENH2 | 0..1 | GEN | Source d'énergie pour le système de production GWAERZH2 correspondant  |
|  GWAERSCEH2 | 0..1 | TEXTE | Provenance de la source d'information pour GENH2  |
|  GENW1 | 0..1 | GEN | Source d'énergie pour le système de production GWAERZW1 correspondant  |
|  GWAERSCEW1 | 0..1 | TEXTE | Provenance de la source d'information pour GENW1  |
|  GENW2 | 0..1 | GEN | Source d'énergie pour le système de production GWAERZW2 correspondant  |

18 / 36

7401

## Page 19

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|  GWAERSCEW2 | 0..1 | TEXTE | Provenance de la source d'information pour GENW2  |
| --- | --- | --- | --- |
|  AE_H1 | 0..1 | TEXTE | Agent énergétique principal pour le chauffage (simplifié)  |
|  AE_H2 | 0..1 | TEXTE | Agent énergétique secondaire pour le chauffage (simplifié)  |
|  AE_W1 | 0..1 | TEXTE | Agent énergétique principal pour l'ECS (simplifié)  |
|  AE_W2 | 0..1 | TEXTE | Agent énergétique secondaire pour l'ECS (simplifié)  |
|  GWAERZH1_RDT | 0..1 | 0.00..3.00 | Rendement du producteur de chaleur AE_H1  |
|  GWAERZH2_RDT | 0..1 | 0.00..3.00 | Rendement du producteur de chaleur AE_H2  |
|  GWAERZW1_RDT | 0..1 | 0.00..3.00 | Rendement du producteur de chaleur AE_W1  |
|  GWAERZW2_RDT | 0..1 | 0.00..3.00 | Rendement du producteur de chaleur AE_W2  |
|  BESOINS_CH | 0..1 | 0..999999999 | Besoins de chaleur calculés pour le chauffage du bâtiment, en kWh/an  |
|  BESOINS_ECS | 0..1 | 0..999999999 | Besoins de chaleur calculés pour l'ECS, en kWh/an  |
|  BESOINS_CH_OPTI | 0..1 | 0..999999999 | Besoins de chaleur optimaux, soit si le bâtiment construit avant 2001 était assaini selon les standards d'une rénovation lourde, en kWh/an  |
|  H1_CO2_DIR | 0..1 | 0..999999999 | Emissions directes (en sortie de cheminée) en kgCO2 pour AE_H1  |
|  H2_CO2_DIR | 0..1 | 0..999999999 | Emissions directes (en sortie de cheminée) en kgCO2 pour AE_H1  |
|  W1_CO2_DIR | 0..1 | 0..999999999 | Emissions directes (en sortie de cheminée) en kgCO2 pour AE_W1  |
|  W2_CO2_DIR | 0..1 | 0..999999999 | Emissions directes (en sortie de cheminée) en kgCO2 pour AE_W2  |
|  H1_CO2_INDIR | 0..1 | 0..999999999 | Emissions indirectes en kgCO2 pour AE_H1  |
|  H2_CO2_INDIR | 0..1 | 0..999999999 | Emissions indirectes en kgCO2 pour AE_H2  |
|  W1_CO2_INDIR | 0..1 | 0..999999999 | Emissions indirectes en kgCO2 pour AE_W1  |
|  W2_CO2_INDIR | 0..1 | 0..999999999 | Emissions indirectes en kgCO2 pour AE_W2  |
|  CO2_DIR_TOT | 0..1 | 0..999999999 | Somme des émissions directes de CO2 en kgCO2  |

19 / 36

7401

## Page 20

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|  CO2_INDIR_TOT | 0..1 | 0..999999999 | Somme des émissions indirectes de CO2 en kgCO2  |
| --- | --- | --- | --- |
|  ID_RECENS_ARCHI | 0..1 | 0..999999999 | Identifiant du recensement architectural de l'objet auquel l'EGID est affilié  |
|  NOTE_RECENS_ARCHI | 0..1 | NOTE_ARCHI | Note du recensement architectural auquel l'EGID est affilié  |
|  ETAT_REGENER | 1 |  | Date de dernière mise en production du RegEnerBat  |
|  CONSO_GWAERZH1 | 0..1 | 0..999999999 | Consommation estimée de la production de chauffage primaire [kWh/an]  |
|  CONSO_GWAERZH2 | 0..1 | 0..999999999 | Consommation estimée de la production de chauffage secondaire [kWh/an]  |
|  CONSO_GWAERZW1 | 0..1 | 0..999999999 | Consommation estimée de la production d'eau chaude primaire [kWh/an]  |
|  CONSO_GWAERZW2 | 0..1 | 0..999999999 | Consommation estimée de la production d'eau chaude secondaire [kWh/an]  |
|  ID_EMPREINTE | 1 | regenergeo |   |

### 4.3.2 Cadastre énergétique des bâtiments vaudois (RegEnerGeo)

|  Nom | Cardinalité | Type | Description  |
| --- | --- | --- | --- |
|  ID_EMPREINTE | 1 | TEXTE | Identifiant de l'empreinte au sol  |
|  TYPE_EMPREINTE | 1 | TYPE_EMPREINTE | Type de l'empreinte au sol (réelle ou fictive)  |
|  SRCE_EMPREINTE | 1 | SOURCE_EMPREINTE | Source de l'empreinte au sol  |
|  GGDENR | 1 | 5400..5940 | Numéro de la commune selon l'Office Fédéral de la statistique  |
|  GGDENAME | 1 | TEXTE | Nom de la commune  |
|  NBRE_EGID | 1 | 0..99 | Nombre d'EGID associés  |
|  ALTI_BAT | 0..1 | 300..4000 | Altitude du bâtiment au rez de chaussée  |
|  GASTW | 0..1 | 0..27 | Nombre d'étages  |
|  GEBF | 0..1 | 0..999999 | Surface de référence énergétique totale  |
|  AFF_SIA | 0..1 | AFF_SIA | Affectation SIA principale  |
|  GKAT | 0..1 | GKAT | Catégorie du bâtiment, selon le RegBL  |
|  GKLAS | 0..1 | GKLAS | Classe du bâtiment, selon le RegBL  |
|  GBAUJ | 0..1 | 1900..2050 | Année de construction de l'EGID  |
|  RENOV_LEGERE_ANNEE | 0..1 | 1900..2050 | Année de dernière rénovation légère de l'EGID  |

20 / 36

7401

## Page 21

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

|  RENOV_LOURDE_ANNEE | 0..1 | 1900..2050 | Année de dernière rénovation lourde de l'EGID  |
| --- | --- | --- | --- |
|  AE_H | 0..1 | TEXTE | Agent énergétique principal pour le chauffage (simplifié)  |
|  AE_W | 0..1 | TEXTE | Agent énergétique principal pour l'eau chaude sanitaire (simplifié)  |
|  BESOINS_CH_OPTI | 0..1 | 0.0..999999999.9 | Besoins de chaleur optimaux, soit si le bâtiment construit avant 2001 était assaini selon les standards d'une rénovation lourde, en kWh/an  |
|  BESOINS_CH | 0..1 | 0.0..999999999.9 | Besoins de chaleur calculés pour le chauffage du bâtiment, en kWh/an  |
|  BESOINS_ECS | 0..1 | 0.0..999999999.9 | Besoins de chaleur calculés pour l'ECS, en kWh/an  |
|  BESOINS_TOT | 0..1 | 0.0..999999999.9 | Besoins de chaleur sommés pour le chauffage et l'ECS, en kWh/an  |
|  CO2_DIR | 0..1 | 0.0..999999999.9 | Somme des émissions directes de CO2, en kgCO2  |
|  CO2_INDIR | 0..1 | 0.0..999999999.9 | Somme des émissions indirectes de CO2, en kgCO2  |
|  Geometrie | 1 | SURFACE | Géométrie de type polygone  |
|  EgidDe | 1..n | regener |   |

### 4.3.3 Métadonnées (MetadataReg)

|  Nom | Cardinalité | Type | Description  |
| --- | --- | --- | --- |
|  DS_NOM | 0..1 | TEXTE | Nom des sources de données  |
|  DS_DATE | 0..1 | XMLDate | Date de dernière extraction des sources de données  |

### 4.3.4 Domaines de valeur

#### 4.3.4.1 AFF_SIA

|  Nom | Description  |
| --- | --- |
|  Non_defini |   |
|  Batiment_non_chauffe |   |
|  Habitat_collectif |   |
|  Habitat_individuel |   |
|  Administration |   |
|  Ecoles |   |
|  Commerce |   |
|  Restauration |   |
|  Lieux_de_rassemblement |   |

21 / 36

7401

## Page 22

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Hopitaux

Industrie

Depots

Installations_sportives

Piscines_couvertes

Activite_non_definie

Logement_non_defini

Information_d_affection_contradictoire

### 4.3.4.2 ENER_EPOQUE

|  Nom | Description  |
| --- | --- |

Avant_1919

De_1919_a_1945

De_1946_a_1960

De_1961_a_1970

De_1971_a_1980

De_1981_a_1985

De_1986_a_1990

De_1991_a_1995

De_1996_a_2000

De_2001_a_2005

De_2006_a_2010

De_2011_a_2015

De_2016_a_2020

De_2021_a_2025

De_2026_a_2030

De_2031_a_2035

### 4.3.4.3 GEN

|  Nom | Description  |
| --- | --- |

Bois_buches

Bois_generique

Mazout

Gaz

Eau

Serpentin_geothermique

Sonde_geothermique

Geothermie_generique

22 / 36

7401

## Page 23

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Air

Aucune

Rejets_thermiques_bat

Bois_dechiquetes_copeaux

Autre

Indeterminee

Chaleur_produite_a_distance_basse_T

Chaleur_produite_a_distance_haute_T

Chaleur_produite_a_distance_generique

Soleil_thermique

Electricite

Bois_granules_pellets

### 4.3.4.4 GKAT

Nom

Description

Constructions_particulieres

Batiment_sans_usage_d_habitation

Batiment_partiellement_a_usage_d_habitation

Batiment_d_habitation_a_usage_annexe

Batiments_exclusivement_a_usage_d_habitation

Habitat_provisoire

### 4.3.4.5 GKLAS

Nom

Description

Autres_batiments_d_hebergement_de_tourisme

Gares_aerogares_et_centres_d_appels

Batiments_commerciaux

Immeubles_de_bureaux

Hotels

Habitat_communautaire

Immeubles_a_trois_logements_et_plus

Maisons_a_deux_logements

Maisons_individuelles

Batiments_industriels

Reservoirs_sites_entrepots

Musees_et_bibliotheques

Batiments_enseignement_et_recherche

Salles_de_sport

23 / 36

7401

## Page 24

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Hopitaux_et_etablissement_de_sante
Batiments_exploitation_agricole
Edifices_culturels_et_religieux
Autres_batiments_non_classes
Monuments_historiques_et_classes
Batiment_a_usage_recreatif_ou_culturel
Autres_batiments_exploitation_agricole
Batiments_pour_cultures_vegetales
Batiments_pour_garde_animaux
Garages
Autres_batiments_hebergement_collectif

### 4.3.4.6 GWAERZH

|  Nom | Description  |
| --- | --- |
|  Autre |   |
|  Echangeur_de_chaleur_plusieurs_bats |   |
|  Echangeur_de_chaleur_un_seul_bat |   |
|  Chauffage_electrique_direct |   |
|  Chauffage_central_electrique_plusieurs_bats |   |
|  Chauffage_central_electrique_un_seul_bat |   |
|  Installation_ccf_plusieurs_bats |   |
|  Installation_ccf_un_seul_bat |   |
|  Poele |   |
|  Chaudiere_a_condensation_pour_plusieurs_batiments |   |
|  Chaudiere_a_condensation_pour_un_seul_batiment |   |
|  Chaudiere_standard_pour_plusieurs_batiments |   |
|  Chaudiere_standard_pour_un_seul_batiment |   |
|  Chaudiere_generique_pour_plusieurs_batiments |   |
|  Chaudiere_generique_pour_un_seul_batiment |   |
|  Installation_solaire_thermique_pour_plusieurs_batiments |   |
|  Installation_solaire_thermique_pour_un_seul_batiment |   |
|  Pompe_a_chaleur_PAC_pour_plusieurs_batiments |   |
|  Pompe_a_chaleur_PAC_pour_un_seul_batiment |   |
|  Pas_de_generateur_de_chaleur |   |

### 4.3.4.7 GWAERZW

|  Nom | Description  |
| --- | --- |
|  Echangeur_de_chaleur_y_compris_CAD  |   |

24 / 36

7401

## Page 25

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Petit_boiler

Boiler_electrique_central

Installation_couplage_chaleur_force

Chaudiere_a_condensation

Chaudiere_standard

Chaudiere_generique

Installation_solaire_thermique

Pompe_a_chaleur_PAC

Pas_de_generateur_de_chaleur

Autre

### 4.3.4.8 NOTE_ARCHI

|  Nom | Description  |
| --- | --- |
|  integration_alterante | Intégration altérante (7)  |
|  sans_interet | Sans intérêt (6)  |
|  integration_mitigee | Intégration mitigée (5)  |
|  integration_adequate | Intégration adéquate (4)  |
|  interet_local | Intérêt local (3)  |
|  interet_regional | Intérêt régional (2)  |
|  interet_national | Intérêt national (1)  |
|  non_evalue | Non évalué (0)  |

### 4.3.4.9 SOURCE_EMPREINTE

|  Nom | Description  |
| --- | --- |
|  DIREN |   |
|  NPCS |   |
|  MOVD |   |

### 4.3.4.10 TYPE_EMPREINTE

|  Nom | Description  |
| --- | --- |
|  Batiment_sous_sol | L'empreinte au sol est effective et correspond à la géométrie des bâtiments enregistrés ayant une correspondance exacte (EGID) avec les bâtiments cadastrés en sous-sol de la MO.  |
|  Batiment_hors_sol | L'empreinte au sol est effective et correspond à la géométrie des bâtiments enregistrés ayant une correspondance exacte (EGID) avec les bâtiments cadastrés hors sol de la MO.  |
|  Batiment_non_cadastre | L'empreinte au sol est fictive et générée sur la base des bâtiments enregistrés n'ayant pas de correspondance exacte (EGID) avec les bâtiments cadastrés par la MO.  |

25 / 36

7401

## Page 26

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

## 5 Annexe

### 5.1 A – Glossaire²

*Géodonnées* : données à référence spatiale qui décrivent l'étendue et les propriétés d'espaces et d'objets donnés à un instant donné, en particulier la position, la nature, l'utilisation et le statut juridique de ces éléments ;

*Géoinformations* : informations à référence spatiale acquises par la mise en relation de géodonnées;

*Géodonnées de base* : géodonnées qui se fondent sur un acte législatif fédéral, cantonal ou communal;

*Géodonnées de base qui lient les autorités* : géodonnées de base qui présentent un caractère juridiquement contraignant pour les autorités fédérales, cantonales et communales dans le cadre de l'exécution de leurs tâches de service public ;

*Géodonnées de référence* : géodonnées de base servant de base géométrique à d'autres géodonnées;

*Géométadonnées* : descriptions formelles des caractéristiques de géodonnées, notamment leur provenance, contenu, structure, validité, actualité ou précision, les droits d'utilisation qui y sont attachés, les possibilités d'y accéder ou les méthodes permettant de les traiter;

*Modèles de géodonnées* : représentations de la réalité fixant la structure et le contenu de géodonnées indépendamment de tout système ;

*Modèles de représentation* : définitions de représentations graphiques destinées à la visualisation de géodonnées (p. ex. sous la forme de cartes et de plans);

*Géoservices* : applications aptes à être mises en réseau et simplifiant l'utilisation des géodonnées par des prestations de services informatisés y donnant accès sous une forme structurée.

### 5.2 B – Glossaire technique³

*UML* : Unified Modeling Language;

*Classe* : la classe représente l'élément central. Elle décrit un ensemble d'objets de même genre;

*Classe abstraite* : c'est une classe dont l'implémentation n'est pas complète. Elle sert de base à d'autres classes dérivées ;

*Classe de structure* : c'est une classe qui spécifie la structure d'un objet. Une géométrie y est associée ;

*Héritage* : il constitue une relation de généralisation, ou spécialisation de propriétés ;

*Association* : relation de faible intensité où les classes impliquées sont indépendantes ;

*Composition* : relation de forte intensité ;

² Tirés de la *LGéo*, état au 31.10.2013 (http://www.admin.ch/opc/fr/classified-compilation/20050726/index.html)

³ Tirés de Eisenhut, C. (2004). *Brève introduction à UML*. Disponible sur: http://www.geo.admin.ch/internet/geoportal/fr/home/topics/geobasedata/models.html

26 / 36

7401

## Page 27

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Agrégation : relation de composition affaiblie ;

Attributs : représentent les propriétés des objets d'une classe. Ils constituent ainsi les données ;

Cardinalité : représente le caractère obligatoire ou optionnel d'un attribut.

### 5.3 C – Fichier modèle INTERLIS MN95

INTERLIS 2.4;

/** 103.1 Cadastre énergétique des bâtiments vaudois
*/
!!@ technicalContact=mailto:info.icdg@vd.ch
MODEL VD_EnergetiqueBatiments_V1_1_0 (fr)
AT "https://www.vd.ch"
VERSION "1.1.0" =
IMPORTS GeometryCHLV95_V2;

TOPIC regenergeo =
OID AS INTERLIS.UUIDOID;

DOMAIN

AFF_SIA = (
    Non_defini,
    Batiment_non_chauffe,
    Habitat_collectif,
    Habitat_individuel,
    Administration,
    Ecoles,
    Commerce,
    Restauration,
    Lieux_de_rassemblement,
    Hopitaux,
    Industrie,
    Depots,
    Installations_sportives,
    Piscines_couvertes,
    Activite_non_definie,
    Logement_non_defini,
    Information_d_affection_contradictoire
);

ENER_EPOQUE = (
    Avant_1919,
    De_1919_a_1945,
    De_1946_a_1960,
    De_1961_a_1970,
    De_1971_a_1980,
    De_1981_a_1985,
    De_1986_a_1990,
    De_1991_a_1995,

27 / 36

7401

## Page 28

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

De_1996_a_2000,
De_2001_a_2005,
De_2006_a_2010,
De_2011_a_2015,
De_2016_a_2020,
De_2021_a_2025,
De_2026_a_2030,
De_2031_a_2035
);

GEN = (
Bois_buches,
Bois_generique,
Mazout,
Gaz,
Eau,
Serpentin_geothermique,
Sonde_geothermique,
Geothermie_generique,
Air,
Aucune,
Rejets_thermiques_bat,
Bois_dechiquetes_copeaux,
Autre,
Indeterminee,
Chaleur_produite_a_distance_basse_T,
Chaleur_produite_a_distance_haute_T,
Chaleur_produite_a_distance_generique,
Soleil_thermique,
Electricite,
Bois_granules_pellets
);

GKAT = (
Constructions_particulieres,
Batiment_sans_usage_d_habitation,
Batiment_partiellement_a_usage_d_habitation,
Batiment_d_habitation_a_usage_annexe,
Batiments_exclusivement_a_usage_d_habitation,
Habitat_provisoire
);

GKLAS = (
Autres_batiments_d_hebergement_de_tourisme,
Gares_aerogares_et_centres_d_appels,
Batiments_commerciaux,
Immeubles_de_bureaux,
Hotels,
Habitat_communautaire,
Immeubles_a_trois_logements_et_plus,
Maisons_a_deux_logements,
Maisons_individuelles,
Batiments_industriels,

28 / 36

7401

## Page 29

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

Reservoirs_sites_entrepots,
Musees_et_bibliotheques,
Batiments_enseignement_et_recherche,
Salles_de_sport,
Hopitaux_et_etablissement_de_sante,
Batiments_exploitation_agricole,
Edifices_culturels_et_religieux,
Autres_batiments_non_classes,
Monuments_historiques_et_classes,
Batiment_a_usage_recreatif_ou_culturel,
Autres_batiments_exploitation_agricole,
Batiments_pour_cultures_vegetales,
Batiments_pour_garde_animaux,
Garages,
Autres_batiments_hebergement_collectif
);

GWAERZH = (
    Autre,
    Echangeur_de_chaleur_plusieurs_bats,
    Echangeur_de_chaleur_un_seul_bat,
    Chauffage_electrique_direct,
    Chauffage_central_electrique_plusieurs_bats,
    Chauffage_central_electrique_un_seul_bat,
    Installation_ccf_plusieurs_bats,
    Installation_ccf_un_seul_bat,
    Poele,
    Chaudiere_a_condensation_pour_plusieurs_batiments,
    Chaudiere_a_condensation_pour_un_seul_batiment,
    Chaudiere_standard_pour_plusieurs_batiments,
    Chaudiere_standard_pour_un_seul_batiment,
    Chaudiere_generique_pour_plusieurs_batiments,
    Chaudiere_generique_pour_un_seul_batiment,
    Installation_solaire_thermique_pour_plusieurs_batiments,
    Installation_solaire_thermique_pour_un_seul_batiment,
    Pompe_a_chaleur_PAC_pour_plusieurs_batiments,
    Pompe_a_chaleur_PAC_pour_un_seul_batiment,
    Pas_de_generateur_de_chaleur
);

GWAERZW = (
    Echangeur_de_chaleur_y_compris_CAD,
    Petit_boiler,
    Boiler_electrique_central,
    Installation_couplage_chaleur_force,
    Chaudiere_a_condensation,
    Chaudiere_standard,
    Chaudiere_generique,
    Installation_solaire_thermique,
    Pompe_a_chaleur_PAC,
    Pas_de_generateur_de_chaleur,
    Autre
);

29 / 36

7401

## Page 30

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

NOTE_ARCHI = (
    /** Intégration altérante (7)
    */
    integration_alterante,
    /** Sans intérêt (6)
    */
    sans_interet,
    /** Intégration mitigée (5)
    */
    integration_mitigee,
    /** Intégration adéquate (4)
    */
    integration_adequate,
    /** Intérêt local (3)
    */
    interet_local,
    /** Intérêt régional (2)
    */
    interet_regional,
    /** Intérêt national (1)
    */
    interet_national,
    /** Non évalué (0)
    */
    non_evalue
);

SOURCE_EMPREINTE = (
    DIREN,
    NPCS,
    MOVD
);

TYPE_EMPREINTE = (

/** L'empreinte au sol est effective et correspond à la géométrie des bâtiments enregistrés ayant une correspondance exacte (EGID) avec les bâtiments cadastrés en sous-sol de la MO.

*/

Batiment_sous_sol,

/** L'empreinte au sol est effective et correspond à la géométrie des bâtiments enregistrés ayant une correspondance exacte (EGID) avec les bâtiments cadastrés hors sol de la MO.

*/

Batiment_hors_sol,

/** L'empreinte au sol est fictive et générée sur la base des bâtiments enregistrés n'ayant pas de correspondance exacte (EGID) avec les bâtiments cadastrés par la MO.

*/

Batiment_non_cadastre

);

CLASS metadatareg =

/** Nom des sources de données

*/

DS_NOM : TEXT*50;

30 / 36

7401

## Page 31

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

/** Date de dernière extraction des sources de données
*/
DS_DATE : INTERLIS.XMLDate;
END metadatareg;

CLASS regener =

/** Identifiant fédéral du bâtiment
*/

EGID : MANDATORY 0 .. 999999999;

/** Coordonnée Est de l'EGID
*/

COORD_X : MANDATORY 2490000 .. 2590000;

/** Coordonnée Nord de l'EGID
*/

COORD_Y : 1110000 .. 1210000;

/** Numéro de la commune selon l'Office Fédéral de la statistique
*/

GGDENR : MANDATORY 5400 .. 6000;

/** Nom de la commune
*/

GGDENAME : MANDATORY TEXT*50;

/** Altitude du bâtiment au rez-de-chaussée
*/

ALTI_BAT : 300 .. 4000;

/** Catégorie du bâtiment, selon le RegBL
*/

GKAT : GKAT;

/** Classe du bâtiment, selon le RegBL
*/

GKLAS : GKLAS;

/** Affectation SIA principale
*/

AFF_SIA_1 : AFF_SIA;

/** Affectation SIA secondaire
*/

AFF_SIA_2 : AFF_SIA;

/** Provenance de l'information - AFF_SIA(1/2)
*/

AFF_SIA_PROV : TEXT*50;

/** Surface de référence énergétique totale
*/

GEBF : 0.0 .. 999999999.9;

/** Provenance de l'information - GEBF
*/

GEBF_PROV : TEXT*50;

/** Part en pourcent de la SRE associée à AFF_SIA_1
*/

GEBF_PART : 0.000 .. 1.000;

/** Source utilisée pour procéder à la répartition de GEBF par affectation
*/

GEBF_PART_PROV : TEXT*50;

/** Surface corrigée de l'EGID en mètre carrés (unité similaire à la surface RegBL)
*/

31 / 36

7401

## Page 32

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

GAREA\_CORR : 0.0 .. 999999.9;  
/\*\* Nombre d'étages  
\*/  
GASTW : 0 .. 30;  
/\*\* Année de construction de l'EGID  
\*/  
GBAUJ : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Epoque énergétique de référence pour le calcul des besoins de chaleur du bâtiment. Si une rénovation lourde est renseignée c'est l'époque de rénovation lourde, sinon l'époque de construction  
\*/  
ENER\_EPOQUE : ENER\_EPOQUE;  
/\*\* Date de dernière rénovation lourde de l'EGID  
\*/  
RENOV\_LOURDE\_DATE : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Date de renseignement de l'information RENOV\_LOURDE\_DATE  
\*/  
RENOV\_LOURDE\_DATE\_DATE : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Date de dernière rénovation légère de l'EGID  
\*/  
RENOV\_LEGERE\_DATE : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Date de renseignement de l'information RENOV\_LEGERE\_DATE  
\*/  
RENOV\_LEGERE\_DATE\_DATE : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Provenance de l'information RENOV\_LOURDE\_DATE  
\*/  
RENOV\_LOURDE\_PROV : TEXT\*50;  
/\*\* Provenance de l'information RENOV\_LEGERE\_DATE  
\*/  
RENOV\_LEGERE\_PROV : TEXT\*50;  
/\*\* Système de production de chauffage principal  
\*/  
GWAERZH1 : GWAERZH;  
/\*\* Part couverte par le système de chauffage principal GWAERZH1  
\*/  
GWAERZH1\_PART : 0.000 .. 1.000;  
/\*\* Date de renseignement de l'information GWAERZH1  
\*/  
GWAERDATH1 : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Système de production de chauffage secondaire (si existant)  
\*/  
GWAERZH2 : GWAERZH;  
/\*\* Date de renseignement de l'information GWAERZH2  
\*/  
GWAERZDATH2 : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Système de production de chauffage principal dédié à l'ECS  
\*/  
GWAERZW1 : GWAERZW;  
/\*\* Part couverte par le système de chauffage principal dédié à l'ECS GWAERZW1  
\*/  
GWAERZW1\_PART : 0.000 .. 1.000;  
/\*\* Date de renseignement de l'information GWAERZW1  
\*/  
GWAERDATW1 : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';

32 / 36

7401

## Page 33

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

/\*\* Système de production de chauffage secondaire dédié à l'ECS (si existant)  
\*/  
GWAERZW2 : GWAERZW;  
/\*\* Date de renseignement de l'information GWAERZW2  
\*/  
GWAERDATW2 : FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Source d'énergie pour le système de production GWAERZH1 correspondant  
\*/  
GENH1 : GEN;  
/\*\* Provenance de la source d'information pour GENH1  
\*/  
GWAERSCEH1 : TEXT\*50;  
/\*\* Source d'énergie pour le système de production GWAERZH2 correspondant  
\*/  
GENH2 : GEN;  
/\*\* Provenance de la source d'information pour GENH2  
\*/  
GWAERSCEH2 : TEXT\*50;  
/\*\* Source d'énergie pour le système de production GWAERZW1 correspondant  
\*/  
GENW1 : GEN;  
/\*\* Provenance de la source d'information pour GENW1  
\*/  
GWAERSCEW1 : TEXT\*50;  
/\*\* Source d'énergie pour le système de production GWAERZW2 correspondant  
\*/  
GENW2 : GEN;  
/\*\* Provenance de la source d'information pour GENW2  
\*/  
GWAERSCEW2 : TEXT\*50;  
/\*\* Agent énergétique principal pour le chauffage (simplifié)  
\*/  
AE\_H1 : TEXT\*50;  
/\*\* Agent énergétique secondaire pour le chauffage (simplifié)  
\*/  
AE\_H2 : TEXT\*50;  
/\*\* Agent énergétique principal pour l'ECS (simplifié)  
\*/  
AE\_W1 : TEXT\*50;  
/\*\* Agent énergétique secondaire pour l'ECS (simplifié)  
\*/  
AE\_W2 : TEXT\*50;  
/\*\* Rendement du producteur de chaleur AE\_H1  
\*/  
GWAERZH1\_RDT : 0.00 .. 3.00;  
/\*\* Rendement du producteur de chaleur AE\_H2  
\*/  
GWAERZH2\_RDT : 0.00 .. 3.00;  
/\*\* Rendement du producteur de chaleur AE\_W1  
\*/  
GWAERZW1\_RDT : 0.00 .. 3.00;  
/\*\* Rendement du producteur de chaleur AE\_W2  
\*/

33 / 36

7401

## Page 34

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

GWAERZW2\_RDT : 0.00 .. 3.00;  
/\*\* Besoins de chaleur calculés pour le chauffage du bâtiment, en kWh/an  
\*/  
BESOINS\_CH : 0 .. 999999999;  
/\*\* Besoins de chaleur calculés pour l'ECS, en kWh/an  
\*/  
BESOINS\_ECS : 0 .. 999999999;  
/\*\* Besoins de chaleur optimaux, soit si le bâtiment construit avant 2001 était assaini selon les standards d'une rénovation lourde, en kWh/an  
\*/  
BESOINS\_CH\_OPTI : 0 .. 999999999;  
/\*\* Emissions directes (en sortie de cheminée) en kgCO2 pour AE\_H1  
\*/  
H1\_CO2\_DIR : 0 .. 999999999;  
/\*\* Emissions directes (en sortie de cheminée) en kgCO2 pour AE\_H1  
\*/  
H2\_CO2\_DIR : 0 .. 999999999;  
/\*\* Emissions directes (en sortie de cheminée) en kgCO2 pour AE\_W1  
\*/  
W1\_CO2\_DIR : 0 .. 999999999;  
/\*\* Emissions directes (en sortie de cheminée) en kgCO2 pour AE\_W2  
\*/  
W2\_CO2\_DIR : 0 .. 999999999;  
/\*\* Emissions indirectes en kgCO2 pour AE\_H1  
\*/  
H1\_CO2\_INDIR : 0 .. 999999999;  
/\*\* Emissions indirectes en kgCO2 pour AE\_H2  
\*/  
H2\_CO2\_INDIR : 0 .. 999999999;  
/\*\* Emissions indirectes en kgCO2 pour AE\_W1  
\*/  
W1\_CO2\_INDIR : 0 .. 999999999;  
/\*\* Emissions indirectes en kgCO2 pour AE\_W2  
\*/  
W2\_CO2\_INDIR : 0 .. 999999999;  
/\*\* Somme des émissions directes de CO2 en kgCO2  
\*/  
CO2\_DIR\_TOT : 0 .. 999999999;  
/\*\* Somme des émissions indirectes de CO2 en kgCO2  
\*/  
CO2\_INDIR\_TOT : 0 .. 999999999;  
/\*\* Identifiant du recensement architectural de l'objet auquel l'EGID est affilié  
\*/  
ID\_RECENS\_ARCHI : 0 .. 999999999;  
/\*\* Note du recensement architectural auquel l'EGID est affilié  
\*/  
NOTE\_RECENS\_ARCHI : NOTE\_ARCHI;  
/\*\* Date de dernière mise en production du RegEnerBat  
\*/  
ETAT\_REGENER : MANDATORY FORMAT INTERLIS.XMLDate '1900-01-01' .. '2050-01-01';  
/\*\* Consommation estimée de la production de chauffage primaire [kWh/an]  
\*/  
CONSO\_GWAERZH1 : 0 .. 999999999;

34 / 36

7401

## Page 35

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

/** Consommation estimée de la production de chauffage secondaire [kWh/an]
*/
CONSO_GWAERZH2 : 0 .. 999999999;
/** Consommation estimée de la production d'eau chaude primaire [kWh/an]
*/
CONSO_GWAERZW1 : 0 .. 999999999;
/** Consommation estimée de la production d'eau chaude secondaire [kWh/an]
*/
CONSO_GWAERZW2 : 0 .. 999999999;
END regener;

CLASS regenergeo =

/** Identifiant de l'empreinte au sol
*/
ID_EMPREINTE : MANDATORY TEXT*50;
/** Type de l'empreinte au sol (réelle ou fictive)
*/
TYPE_EMPREINTE : MANDATORY TYPE_EMPREINTE;
/** Source de l'empreinte au sol
*/
SRCE_EMPREINTE : MANDATORY SOURCE_EMPREINTE;
/** Numéro de la commune selon l'Office Fédéral de la statistique
*/
GGDENR : MANDATORY 5400 .. 5940;
/** Nom de la commune
*/
GGDENAME : MANDATORY TEXT*50;
/** Nombre d'EGID associés
*/
NBRE_EGID : MANDATORY 0 .. 99;
/** Altitude du bâtiment au rez de chaussée
*/
ALTI_BAT : 300 .. 4000;
/** Nombre d'étages
*/
GASTW : 0 .. 27;
/** Surface de référence énergétique totale
*/
GEBF : 0 .. 999999;
/** Affectation SIA principale
*/
AFF_SIA : AFF_SIA;
/** Catégorie du bâtiment, selon le RegBL
*/
GKAT : GKAT;
/** Classe du bâtiment, selon le RegBL
*/
GKLAS : GKLAS;
/** Année de construction de l'EGID
*/
GBAUJ : 1900 .. 2050;
/** Année de dernière rénovation légère de l'EGID
*/

35 / 36

7401

## Page 36

Direction du cadastre et de la géoinformation

Modèle de géodonnées minimal

RENOV_LEGERE_ANNEE : 1900 .. 2050;
/** Année de dernière rénovation lourde de l'EGID
*/
RENOV_LOURDE_ANNEE : 1900 .. 2050;
/** Agent énergétique principal pour le chauffage (simplifié)
*/
AE_H : TEXT*50;
/** Agent énergétique principal pour l'eau chaude sanitaire (simplifié)
*/
AE_W : TEXT*50;
/** Besoins de chaleur optimaux, soit si le bâtiment construit avant 2001 était assaini selon les standards d'une rénovation lourde, en kWh/an
*/
BESOINS_CH_OPTI : 0.0 .. 999999999.9;
/** Besoins de chaleur calculés pour le chauffage du bâtiment, en kWh/an
*/
BESOINS_CH : 0.0 .. 999999999.9;
/** Besoins de chaleur calculés pour l'ECS, en kWh/an
*/
BESOINS_ECS : 0.0 .. 999999999.9;
/** Besoins de chaleur sommés pour le chauffage et l'ECS, en kWh/an
*/
BESOINS_TOT : 0.0 .. 999999999.9;
/** Somme des émissions directes de CO2, en kgCO2
*/
CO2_DIR : 0.0 .. 999999999.9;
/** Somme des émissions indirectes de CO2, en kgCO2
*/
CO2_INDIR : 0.0 .. 999999999.9;
/** Géométrie de type polygone
*/
Geométrie : MANDATORY SURFACE WITH (ARCS,STRAIGHTS) VERTEX GeometryCHLV95_V2.Coord2 WITHOUT OVERLAPS>0.001;
END regenergeo;

ASSOCIATION RelCad =
EgidDe -- {1..*} regener;
ID_EMPREINTE -<#> {1} regenergeo;
END RelCad;

END regenergeo;

END VD_EnergetiqueBatiments_V1_1_0.

36 / 36

7401