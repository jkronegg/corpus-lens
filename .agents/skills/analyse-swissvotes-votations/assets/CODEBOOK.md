---
titre: "CODEBOOK"
source: "C:\Users\Julien\git\kronegg\histoire_suisse\.agents\skills\analyse-swissvotes-votations\assets\CODEBOOK.pdf"
date_extraction: "2026-05-24T00:06:22.312465"
pages: "49"
transformation_by: "skill extract-pdf-to-md"
language_distribution: "de:86, fr:14, en:0"
---
Pages détectées: 1, 2, 3, 1848, 1849, 1850, 1851, 1852, 1853, 1854, 1855, 1856, 1857, 1858, 1859, 1860, 1861, 1862, 1863, 1864, 1865, 1848, 1849, 1850, 1851, 1852, 1853, 1848, 1849, 1850, 100, 101, 102, 103, 104, 105, 106, 107, 108, 1848, 1849, 1850, 1851, 1852, 1853, 1848, 1977, 1977, 1978

## Page 1

Codebuch



Swissvotes – die Datenbank der eidgenössischen Volksabstimmungen









Dieses Codebuch ist lizenziert als "Creative Commons Attribution 4.0 International" (CC BY 4.0). Wir empfehlen die untenstehende Zitierweise.
Empfohlene Zitierweise: Swissvotes (2025): Codebuch für Swissvotes – die Datenbank der eidgenössischen Volksabstimmungen. Année Politique Suisse, Universität Bern. Online: www.swissvotes.ch. Abgerufen am [Datum].

## Page 2

Inhalt dieses Codebuchs

Variablen und Codes im Excel-Datensatz und in der Onlineversion von Swissvotes .................................................................................................. 3 Allgemeines ..................................................................................................................................................................................................................................... 3
Behandlung durch Bundesrat und Parlament .................................................................................................................................................................................11
Sammlung und Einreichung der Unterschriften ............................................................................................................................................................................ 16 Abstimmungskampf ........................................................................................................................................................................................................................ 21
Abstimmungsergebnis ................................................................................................................................................................................................................... 34 Nachbefragung .............................................................................................................................................................................................................................. 39
Quellen der Originaldokumente von Behörden und weiterer herunterladbarer Dokumente in der Detailansicht zu jeder Abstimmungsvorlage ...... 40
Bibliographische Angaben und Links zu den erwähnten Quellen ............................................................................................................................ 49

















Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       2

## Page 3

Variablen und Codes im Excel-Datensatz und in der Onlineversion von Swissvotes

Allgemeines

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Abstimmungs-<br>nummer | anr | Nummer der Abstimmung gemäss Bundesamt für Statistik | Bundesamt für Statistik. |
| Abstimmungsda-<br>tum | datum | Datum des Abstimmungstags | Schweizerische Bundeskanzlei (online). |
|  | titel_kurz_d | Kurzversion des offiziellen Titels der Vorlage (deutsch) | Bundesamt für Statistik;<br>Erläuterungen des Bundesrats («Abstimmungs-<br>büchlein», ab 1977);<br>Swissvotes (eigene Kürzung). |
|  | titel_kurz_f | Kurzversion des offiziellen Titels der Vorlage (französisch) |  |
|  | titel_kurz_e | Kurzversion des Vorlagentitels (englisch) | Swissvotes (eigene Übersetzung) unter Beizug<br>von www.c2d.ch und den Websites der Bundes-<br>behörden |
| Offizieller Titel | titel_off_d | Offizieller Titel der Vorlage (deutsch) | Schweizerische Bundeskanzlei (online). |
| Titre officiel | titel_off_f | Offizieller Titel der Vorlage (französisch) |  |
| Schlagwort | stichwort | Umgangssprachlich gängige Bezeichnung der Vorlage oder<br>zusätzliche Inhaltsangabe | Swissvotes (eigene Recherchen). |
|  | swissvoteslink | Direktlink zur Detailansicht der Vorlage auf Swissvotes | Swissvotes |
|  | anzahl | Anzahl eidgenössischer Vorlagen am selben Datum<br>(Initiativen mit Gegenvorschlag und Stichfrage werden zusammen<br>als eine Vorlage gezählt) | Swissvotes (eigene Erfassung). |




























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       3

## Page 1848

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Rechtsform | rechtsform | Rechtsform der Abstimmungsvorlage<br><br>1 Obligatorisches Referendum<br>2 Fakultatives Referendum<br>3 Volksinitiative<br>4 Direkter Gegenentwurf zu einer Volksinitiative<br>5 Stichfrage (seit 1987 bei Gegenüberstellung von Volksinitiati-<br>ven und Gegenentwürfen) | Schweizerische Bundeskanzlei (online). |
|  | init_formul | Rechtliche Form der Volksinitiativen<br><br>1 Ausformulierter Entwurf für Teilrevision der Verfassung<br>2 Allgemeine Anregung für Teilrevision der Verfassung<br>3 Initiative für Totalrevision der Verfassung<br>9999 Keine Volksinitiative | Schweizerische Bundeskanzlei (online). |
| Kurzbeschrei-<br>bung Swissvotes | kurzbetitel | Titel der Kurzbeschreibung von Swissvotes zur jeweiligen<br>Abstimmung. | Abstimmungen seit 2008: Swissvotes (eigene Er-<br>arbeitung).<br>Abstimmungen 1848-2007: Linder et al. (2010). |
| Beschreibung<br>Année Politique<br>Suisse | anneepolitique | Link zur Beschreibung der Ereignisse rund um die Abstim-<br>mungsvorlage bei Année Politique Suisse. | Année Politique Suisse |
| Offizielle Chro-<br>nologie | bkchrono-de,<br>bkchrono-fr | Link zur Seite der Bundeskanzlei mit der chronologischen<br>Auflistung der amtlichen Ablaufschritte (deutsch- und<br>französischsprachige Version). | Schweizerische Bundeskanzlei (online) |
| Politikbereich | d1e1<br>d1e2<br>d1e3 | Betroffene Politikbereiche<br><br>1 Staatsordnung<br>1.1 Nationale Identität<br>1.2 Politisches System<br>1.2.1 Bundesverfassung<br>1.2.2 Verfassungsgebungsverfahren<br>1.2.3 Gesetzgebungsverfahren | Swissvotes (eigene Zuteilung unter Rücksprache<br>mit dem Bundesamt für Statistik); Kriterium für<br>die Zuteilung ist eine qualitative Beurteilung der<br>Hauptstossrichtungen und zentralen Konflikt-<br>punkte der jeweiligen Vorlage gemäss ihrem<br>Wortlaut und der Medienberichterstattung dazu.<br>In Zweifelsfällen fliessen ergänzend die «The- |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       4

## Page 1849

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 1.2.4 Wahlsystem<br>1.3 Institutionen<br>1.3.1 Regierung, Verwaltung<br>1.3.2 Parlament<br>1.3.3 Gerichte<br>1.3.4 Nationalbank<br>1.4 Volksrechte<br>1.4.1 Initiative<br>1.4.2 Referendum<br>1.4.3 Stimmrecht<br>1.5 Föderalismus<br>1.5.1 Territorialfragen<br>1.5.2 Beziehungen zwischen Bund und Kantonen<br>1.5.3 Aufgabenteilung<br>1.6 Rechtsordnung<br>1.6.1 Internationales Recht<br>1.6.2 Grundrechte<br>1.6.3 Bürgerrecht<br>1.6.4 Privatrecht<br>1.6.5 Strafrecht<br>1.6.6 Datenschutz<br><br>2 Aussenpolitik<br>2.1 Aussenpolitische Grundhaltung<br>2.1.1 Neutralität<br>2.1.2 Unabhängigkeit<br>2.1.3 Gute Dienste<br>2.2 Europapolitik<br>2.2.1 EFTA<br>2.2.2 EU<br>2.2.3 EWR<br>2.2.4 Andere europäische Organisationen<br>2.3 Internationale Organisationen | mengebiete» bei Curia Vista ein sowie der As-<br>pekt, welcher parlamentarischen Kommission<br>und welchem Departement die Vorlage zugeteilt<br>ist. |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       5

## Page 1850

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 2.3.1 UNO<br>2.3.2 Andere internationale Organisationen<br>2.4 Entwicklungszusammenarbeit<br>2.5 Staatsverträge mit einzelnen Staaten<br>2.6 Aussenwirtschaftspolitik<br>2.6.1 Exportförderung<br>2.6.2 Zollwesen<br>2.7 Diplomatie<br>2.8 Auslandschweizer:innen<br><br>3 Sicherheitspolitik<br>3.1 Öffentliche Sicherheit<br>3.1.1 Bevölkerungsschutz<br>3.1.2 Staatsschutz<br>3.1.3 Polizei<br>3.2 Armee<br>3.2.1 Armee (allgemein)<br>3.2.2 Militärorganisation<br>3.2.3 Rüstung<br>3.2.4 Militäranlagen<br>3.2.5 Dienstverweigerung, Zivildienst<br>3.2.6 Armeeabschaffung<br>3.2.7 Militärische Ausbildung<br>3.2.8 Internationale Einsätze<br>3.3 Landesversorgung<br>4 Wirtschaft<br>4.1 Wirtschaftspolitik<br>4.1.1 Konjunkturpolitik<br>4.1.2 Wettbewerbspolitik<br>4.1.3 Strukturpolitik<br>4.1.4 Preispolitik<br>4.1.5 Konsumentenschutz<br>4.1.6 Gesellschaftsrecht |  |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       6

## Page 1851

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 4.2 Arbeit und Beschäftigung<br>4.2.1 Arbeitsbedingungen<br>4.2.2 Arbeitszeit<br>4.2.3 Sozialpartnerschaft<br>4.2.4 Beschäftigungspolitik<br>4.3 Finanzwesen<br>4.3.1 Geld- und Währungspolitik<br>4.3.2 Banken, Börsen, Versicherungen<br>4.4 Freizeit und Tourismus<br>4.4.1 Fremdenverkehr<br>4.4.2 Hotellerie und Gastgewerbe<br>4.4.3 Geldspiele<br><br>5 Landwirtschaft<br>5.1 Agrarpolitik<br>5.2 Tierische Produktion<br>5.3 Pflanzliche Produktion<br>5.4 Forstwirtschaft<br>5.5 Fischerei, Jagd, Haustiere<br>6 Öffentliche Finanzen<br>6.1 Steuerwesen<br>6.1.1 Steuerpolitik<br>6.1.2 Steuersystem<br>6.1.3 Direkte Steuern<br>6.1.4 Indirekte Steuern<br>6.2 Finanzordnung<br>6.3 Öffentliche Ausgaben<br>6.4 Spar- und Sanierungsmassnahmen<br>7 Energie<br>7.1 Energiepolitik<br>7.2 Kernenergie<br>7.3 Wasserkraft |  |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       7

## Page 1852

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 7.4 Alternativenergien<br>7.5 Erdöl, Gas<br><br>8 Verkehr und Infrastruktur<br>8.1 Verkehrspolitik<br>8.1.1 Agglomerationsverkehr<br>8.1.2 Transitverkehr<br>8.2 Strassenverkehr<br>8.2.1 Strassenbau<br>8.2.2 Schwerverkehr<br>8.3 Schienenverkehr<br>8.3.1 Güterverkehr<br>8.3.2 Personenverkehr<br>8.4 Luftverkehr<br>8.5 Schifffahrt<br>8.6 Post<br>8.7 Telekommunikation<br>9 Umwelt und Lebensraum<br>9.1 Boden<br>9.1.1 Raumplanung<br>9.1.2 Bodenrecht<br>9.2 Wohnen<br>9.2.1 Mietwesen<br>9.2.2 Wohnungsbau, Wohneigentum<br>9.3 Umwelt<br>9.3.1 Umweltpolitik<br>9.3.2 Lärmschutz<br>9.3.3 Luftreinhaltung<br>9.3.4 Gewässerschutz<br>9.3.5 Bodenschutz<br>9.3.6 Abfälle<br>9.3.7 Natur- und Heimatschutz<br>9.3.8 Tierschutz |  |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       8

## Page 1853

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 10 Sozial- und Gesellschaftspolitik<br>10.1 Gesundheit<br>10.1.1 Gesundheitspolitik<br>10.1.2 Medizinforschung und –technik<br>10.1.3 Medikamente<br>10.1.4 Suchtmittel<br>10.1.5 Fortpflanzungsmedizin<br>10.2 Sozialversicherungen<br>10.2.1 Alters- und Hinterbliebenenversicherung<br>10.2.2 Invalidenversicherung<br>10.2.3 Berufliche Vorsorge<br>10.2.4 Kranken- und Unfallversicherung<br>10.2.5 Mutterschaftsversicherung<br>10.2.6 Arbeitslosenversicherung<br>10.2.7 Erwerbsersatzordnung<br>10.2.8 Fürsorge<br>10.3 Gesellschaftsfragen<br>10.3.1 Migrations- und Integrationspolitik<br>10.3.2 Asylpolitik<br>10.3.3 Frauen und Gleichstellungspolitik<br>10.3.4 Familienpolitik<br>10.3.5 Kinder- und Jugendpolitik<br>10.3.6 Alterspolitik<br>10.3.7 Menschen mit Behinderungen<br>10.3.8 LGBTQIA+<br>11 Bildung und Forschung<br>11.1 Bildungspolitik<br>11.2 Schulen<br>11.3 Hochschulen<br>11.4 Forschung<br>11.4.1 Gentechnologie<br>11.4.2 Tierversuche |  |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       9

## Page 1854

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  |  | 11.5 Berufsbildung<br>12 Kultur, Religion, Medien<br>12.1 Kulturpolitik<br>12.2 Sprachpolitik<br>12.3 Religion, Kirchen<br>12.4 Sport<br>12.5 Medien und Kommunikation<br>12.5.1 Medienpolitik<br>12.5.2 Presse<br>12.5.3 Radio, Fernsehen, Elektronische Medien<br>12.5.4 Medienfreiheit |  |
| Politikbereich | d2e1<br>d2e2<br>d2e3 | wie d1e1 / d1e2 / d1e3 | Bundesamt für Statistik;<br>Swissvotes (eigene Zuteilung). |
| Politikbereich | d3e1<br>d3e2<br>d3e3 | wie d1e1 / d1e2 / d1e3 | Bundesamt für Statistik;<br>Swissvotes (eigene Zuteilung). |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       10

## Page 1855

Behandlung durch Bundesrat und Parlament

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  | dep | Federführendes Departement des Bundesrats<br><br>1 Eidgenössisches Departement für auswärtige Angelegenhei-<br>ten (EDA)1<br>2 Eidgenössisches Departement des Innern (EDI)2<br>3 Eidgenössisches Justiz- und Polizeidepartement (EJPD)3<br>4 Eidgenössisches Departement für Verteidigung, Bevölke-<br>rungsschutz und Sport (VBS)4<br>5 Eidgenössisches Finanzdepartement (EFD)5<br>6 Eidgenössisches Departement für Wirtschaft, Bildung und<br>Forschung (WBF)6<br>7 Eidgenössisches Departement für Umwelt, Verkehr, Energie<br>und Kommunikation (UVEK)7<br>8 Schweizerische Bundeskanzlei (BK) | Schweizerische Bundeskanzlei.<br>Parlamentsdienste der Schweizerischen<br>Bundes-<br>versammlung (online). |




















1 1848–1888: Politisches Departement. – 1888–1896: Departement des Äusseren. – 1896–1979: Politisches Departement. – Seit 1979: Eidgenössisches Departement für auswärtige Angele heiten.
2 1848–1979: Departement des Innern. – Seit 1979: Eidgenössisches Departement des Innern.
3 1848–1979: Justiz- und Polizeidepartement. – Seit 1979: Eidgenössisches Justiz- und Polizeidepartement.
4 1848–1979: Militärdepartement. – 1979–1998: Eidgenössisches Militärdepartement. – Seit 1998: Eidgenössisches Departement für Verteidigung, Bevölkerungsschutz und Sport.
5 1848–1873: Finanzdepartement. – 1873–1979: Finanz- und Zolldepartement. – Seit 1979: Eidgenössisches Finanzdepartement.
6 1848–1873: Handels- und Zolldepartement. – 1873–1879: Eisenbahn- und Handelsdepartement. – 1879–1888: Handels- und Landwirtschaftsdepartement. – 1888–1896: IndustrieLandwirtschaftsdepartement. – 1896–1915: Handels-, Industrie- und Landwirtschaftsdepartement. – 1915–1979: Volkswirtschaftsdepartement. – 1979-2012: Eidgenössisches Volks schaftsdepartement. – Seit 2013: Eidgenössisches Departement für Wirtschaft, Bildung und Forschung.
7 1848–1860: Post- und Baudepartement. – 1860–1873: Postdepartement. – 1873–1879: Post- und Telegraphendepartement. – 1879–1963: Post- und Eisenbahndepartement. – 1963–1 Verkehrs- und Energiewirtschaftsdepartement. – 1979–1998: Eidgenössisches Verkehrs- und Energiewirtschaftsdepartement. – Seit 1998: Eidgenössisches Departement für Umwelt, kehr, Energie und Kommunikation.
Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern
genund wirt- 979:
Ver-

11

## Page 1856

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Position des<br>Bundesrats | br-pos | Position des Bundesrats zur Vorlage<br>(Position, die der Bundesrat im Abstimmungskampf vertrat, also<br>nach der Beratung im Parlament. In einzelnen Fällen weicht diese<br>von der Position in der bundesrätlichen Botschaft ans Parlament<br>ab.)<br><br>1 Befürwortend<br>2 Ablehnend<br>3 Keine<br>8 Vorzug für den Gegenentwurf (bei Stichfragen)<br>9 Vorzug für die Volksinitiative (bei Stichfragen)<br>. Missing | Erläuterungen des Bundesrats («Abstimmungs-<br>büchlein», ab 1977);<br>Bundesblatt;<br>Année Politique Suisse;<br>Linder et al. 2010. |
|  | legislatur | Nummer der Legislatur, in der die Abstimmung stattfand<br>(gerechnet von Nationalratswahl bis Nationalratswahl) | Parlamentsdienste der Schweizerischen Bundes-<br>versammlung (online). |
|  | legisjahr | Zeitspanne der Legislatur, in der die Abstimmung stattfand | Parlamentsdienste der Schweizerischen Bundes-<br>versammlung (online). |
| Geschäftsnum-<br>mer | gesch_nr | Geschäftsnummer im Parlament | Amtliches Bulletin des National- und Ständerats<br>(ab 1891) |
|  | entwurf_nr | Nummer jenes Entwurfs aus der parlamentarischen Be-<br>handlung, welcher schliesslich zur Volksabstimmung kam;<br>Nummerierung gemäss der Liste der Entwürfe zum jeweili-<br>gen Geschäft auf der Website des Bundesparlaments<br>(vorhanden für Geschäfte, die ab 1994 vom Parlament verab-<br>schiedet wurden) | Parlamentsdienste der Schweizerischen Bundes-<br>versammlung (online). |
| (Geschäftsnum-<br>mer) | curiavista-de,<br>curiavista-fr | Link zur Seite des Bundesparlaments mit allen Unterlagen<br>zur Behandlung des Geschäfts im Parlament (deutsch-<br>bzw. französischsprachige Version)<br>(ab 1970 vorhanden; für Vorlagen, die vor 1995 im Parlament be-<br>handelt wurden, werden unter dem Link nur die Fundstellen in<br>den Originalquellen (Amtliches Bulletin und Bundesblatt) ange-<br>zeigt) | Parlamentsdienste der Schweizerischen Bundes-<br>versammlung (online). |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       12

## Page 1857

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  | pa-iv | Parlamentarische Initiativen<br><br>0 Abstimmungsvorlage geht nicht auf eine parlamentarische<br>Initiative zurück (inkl. direkte Gegenentwürfe, die mittels<br>parlamentarischer Initiative eingebracht wurden, ihren Ur-<br>sprung aber in einer Volksinitiative haben)<br>1 Abstimmungsvorlage geht auf eine parlamentarische Initia-<br>tive zurück | Bundesblatt;<br>Linder et al. 2010;<br>Année Politique Suisse. |
| Position des Par-<br>laments | bv-pos | Position des Parlaments zur Vorlage<br><br>1 Befürwortend<br>2 Ablehnend<br>3 Keine Abstimmungsempfehlung des Parlaments (aufgrund<br>gegensätzlicher Haltungen der beiden Kammern oder bei<br>Vorliegen einer Volksinitiative auf Totalrevision der Bundes-<br>verfassung)<br>8 Vorzug für den Gegenentwurf (bei Stichfragen) | Amtliches Bulletin des National- und Ständerats<br>(ab 1891);<br>Bundesblatt;<br>Erläuterungen des Bundesrats («Abstimmungs-<br>büchlein», ab 1977). |
| Position des Na-<br>tionalrats | nr-pos | Position des Nationalrats zur Vorlage<br><br>1 Befürwortende Mehrheit im Nationalrat<br>2 Ablehnende Mehrheit im Nationalrat<br>3 Keine Abstimmungsempfehlung des Nationalrats (wenn es<br>aufgrund gegensätzlicher Haltungen der beiden Kammern zu<br>keiner Schlussabstimmung kam oder bei Vorliegen einer<br>Volksinitiative auf Totalrevision der Bundesverfassung)<br>8 Vorzug für den Gegenentwurf (bei Stichfragen) | Amtliches Bulletin des Nationalrats (ab 1891);<br>Funk 1925 (für 1874 bis 1914). |
| (Position des Na-<br>tionalrats) | nrja,<br>nrnein | Anzahl Ja- und Nein-Stimmen in der Schlussabstimmung<br>im Nationalrat<br>Bei ursprünglicher Stimmengleichheit wird der Stichentscheid<br>des Präsidiums dem jeweiligen Lager zugerechnet.<br>Bei Stichfragen: nrja = Stimmen für die Volksinitiative, nrnein =<br>Stimmen für den Gegenentwurf | Amtliches Bulletin des Nationalrats (ab 1891);<br>Funk 1925 (für 1874 bis 1914). |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       13

## Page 1858

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Position des<br>Ständerats | sr-pos | Position des Ständerats zur Vorlage<br><br>1 Befürwortende Mehrheit im Ständerat<br>2 Ablehnende Mehrheit im Ständerat<br>3 Keine Abstimmungsempfehlung des Ständerats (wenn es auf-<br>grund gegensätzlicher Haltungen der beiden Kammern zu<br>keiner Schlussabstimmung kam oder bei Vorliegen einer<br>Volksinitiative auf Totalrevision der Bundesverfassung)<br>8 Vorzug für den Gegenentwurf (bei Stichfragen) | Amtliches Bulletin des Ständerats (ab 1891);<br>Funk 1925 (für 1874 bis 1914). |
| (Position des<br>Ständerats) | srja,<br>srnein | Anzahl Ja- und Nein-Stimmen in der Schlussabstimmung<br>im Ständerat<br>Bei ursprünglicher Stimmengleichheit wird der Stichentscheid<br>des Präsidiums dem jeweiligen Lager zugerechnet.<br>Bei Stichfragen: srja = Stimmen für die Volksinitiative, srnein =<br>Stimmen für den Gegenentwurf. | Amtliches Bulletin des Ständerats (ab 1891);<br>Funk 1925 (für 1874 bis 1914). |
|  | dat-message | Datum, an dem der Bundesrat seine Botschaft zuhanden<br>des Parlaments zur Vorlage verabschiedete.<br>Bei Vorlagen, die auf eine Parlamentarische Initiative zurückge-<br>hen: Datum der bundesrätlichen Stellungnahme zur Parlamenta-<br>rischen Initiative<br>. Missing | Bundesblatt. |
|  | dat-parl | Datum der Verabschiedung der Vorlage durch das Parla-<br>ment.<br>(Entspricht dem Datum der Schlussabstimmung im Zweitrat.)<br>. Missing | Bundesblatt;<br>Amtliches Bulletin des National- und Ständerats. |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       14

## Page 1859

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  | dat-force | Datum, an dem die Vorlage in Kraft trat.<br><br>0 Kein Inkrafttreten der Vorlage, weil diese in der Volksabstim-<br>mung abgelehnt wurde.<br>. Missing | Bundesblatt;<br>Bundeskanzlei (online). |
| Behandlungs-<br>dauer Parlament | dauer_bv | Behandlungsdauer im Parlament: Anzahl Tage von der Ver-<br>abschiedung der bundesrätlichen Botschaft bis zum Be-<br>schluss des Parlaments.<br>Geht die Vorlage auf eine parlamentarische Initiative zu-<br>rück, wird ein fehlender Wert (.) ausgewiesen. | Swissvotes (eigene Berechnung). |
|  | dauer_abst | Anzahl Tage vom Parlamentsbeschluss bis zum Tag der<br>Volksabstimmung | Swissvotes (eigene Berechnung). |
|  | i-dauer_tot | Nur bei Volksinitiativen: Anzahl Tage ab der Einreichung<br>bis zum Tag der Volksabstimmung<br>Sonderfälle: Bei den Vorlagen Nr. 665, 666 und 671 galt während<br>der Unterschriftensammlung ein 72-tägiger Fristenstillstand.<br>Diese 72 Tage wurden für die Berechnung von i-dauer_tot nicht<br>mitgezählt (Details siehe unter i-dauer_samm). | Swissvotes (eigene Berechnung). |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       15

## Page 1860

Sammlung und Einreichung der Unterschriften

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Urheber:innen | urheber,<br>urheber-fr | Nur bei Volksinitiativen und fakultativen Referenden: Or-<br>ganisationen, Gruppierungen oder Personen, die die Ini-<br>tiative formuliert und/oder die Unterschriftensammlung<br>angeführt haben (auf Deutsch bzw. Französisch)<br>Bei direkten Gegenentwürfen werden die Urheber:innen der<br>Volksinitiative genannt, die zum Gegenentwurf geführt hat. | Schweizerische Bundeskanzlei (online);<br>Année Politique Suisse;<br>Linder et al. (2010);<br>Bolliger (2007);<br>Zürcher (2006);<br>Swissvotes. |
|  | dat-preexam | Datum der Vorprüfung der Initiative.<br>(Nur bei Volksinitiativen, die nach dem 1.7.1978 lanciert wur-<br>den.)<br><br>0 Keine Vorprüfung (Volksinitiativen, die vor dem 1.7.1978 lan-<br>ciert wurden, sowie Referenden) | Bundesblatt. |
|  | dat-start | Beginn der Sammelfrist: erster Tag der Unterschriften-<br>sammlung.<br>(Nur bei Volksinitiativen und fakultativen Referenden.)<br>Bei fakultativen Referenden entspricht dies dem Datum der<br>amtlichen Veröffentlichung des Erlasses.<br><br>0 Keine Unterschriftensammlung (obligatorische Referenden) | Bundesblatt;<br>Bundeskanzlei (online). |
|  | dat-limit | Ende der Sammelfrist: letztmögliches Datum zur Einrei-<br>chung der Unterschriften.<br>(Nur bei Volksinitiativen, die nach dem 1.7.1978 lanciert wurden,<br>sowie bei fakultativen Referenden.)<br>. Missing<br>9999 Keine Begrenzung der Sammelfrist (Volksinitiativen, die<br>vor dem 1.7.1978 lanciert wurden)<br><br>0 Keine Unterschriftensammlung (obligatorische Referen-<br>den) | Bundeskanzlei (online). |































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       16

## Page 1861

|    | sammelfrist   | Anzahl Tage, die zum Sammeln von Unterschriften zur                 | Volksinitiativen ab 1978: eigene Berechnung        |
|    |               | Verfügung standen.                                                  | durch Swissvotes auf Basis der Daten der Bun-      |
|    |               | (Nur bei Volksinitiativen, die nach dem 1.7.1978 lanciert wurden,   | deskanzlei (online).                               |
|    |               | sowie bei fakultativen Referenden.)                                 | Übrige Vorlagen: Bundesverfassung, Bundesge-       |
|    |               | 9999 Keine Begrenzung der Sammelfrist (Volksinitiativen, die        | setz über die politischen Rechte vom 17.12.1976.   |
|    |               | vor dem 1.7.1978 lanciert wurden)                                   |                                                    |
|    |               | 0 Keine Unterschriftensammlung (obligatorische Referen-             |                                                    |
|    |               | den)                                                                |                                                    |
|    |               | Sonderfälle: Siehe i-dauer_samm                                     |                                                    |
|:---|:--------------|:--------------------------------------------------------------------|:---------------------------------------------------|
|    | unter-quorum  | Massgebliches Unterschriftenquorum: Anzahl gültiger                 | Bundesblatt (Beschluss über das Zustandekom-       |
|    |               | Unterschriften, die für das Zustandekommen der Volks-               | men).                                              |
|    |               | initiative bzw. des fakultativen Referendums erforderlich           |                                                    |
|    |               | war.                                                                |                                                    |
|    |               | 0 Keine Unterschriftensammlung (obligatorische Referenden)          |                                                    |
|    | dat-submit    | Datum, an dem die Unterschriften eingereicht wurden.                | Bundeskanzlei (online).                            |
|    |               | . Missing                                                           |                                                    |
|    |               | 0 Keine Unterschriftensammlung (obligatorische Referenden)          |                                                    |
|    | dat-success   | Datum des Bundesratsbeschlusses über das Zustande-                  | Bundesblatt.                                       |
|    |               | kommen.                                                             |                                                    |
|    |               | (Offizielle Feststellung, dass fristgerecht die benötigte Anzahl    |                                                    |
|    |               | gültiger Unterschriften eingereicht worden ist; nur bei Volks-      |                                                    |
|    |               | initiativen und fakultativen Referenden.)                           |                                                    |
|    |               | . Missing                                                           |                                                    |
|    |               | 0 Keine Unterschriftensammlung (obligatorische Referenden)          |                                                    |





























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       17

## Page 1862

| Sammeldauer   | i-dauer_samm   | Nur bei Volksinitiativen: Anzahl Tage ab Sammelbeginn             | Swissvotes (eigene Berechnung).   |
|               |                | bis zur Einreichung der Initiative                                |                                   |
|               |                | Sonderfälle: Im Rahmen der Massnahmen gegen die Covid-19-         |                                   |
|               |                | Pandemie beschloss der Bundesrat in der Verordnung vom 20.        |                                   |
|               |                | März 2020 über den Fristenstillstand bei eidgenössischen          |                                   |
|               |                | Volksbegehren (AS 2020 847), dass die Sammelfristen bei           |                                   |
|               |                | Volksinitiativen vom 21.3.2020 bis und mit 31.5.2020, also wäh-   |                                   |
|               |                | rend 72 Tagen, stillstanden. Der Ablauf der Sammelfrist ver-      |                                   |
|               |                | schob sich damit um 72 Tage, und während dieser Zeit durften      |                                   |
|               |                | keine Unterschriften für die Initiativen gesammelt werden. Im     |                                   |
|               |                | Swissvotes-Datensatz wurden diese 72 Tage für die Berechnung      |                                   |
|               |                | der eingesetzten Sammeldauer nicht mitgezählt. Betroffen von      |                                   |
|               |                | dieser Regelung waren die Vorlagen Nr. 665, 666 und 671.          |                                   |
|:--------------|:---------------|:------------------------------------------------------------------|:----------------------------------|
|               | i-dauer_br     | Nur bei Volksinitiativen: Anzahl Tage ab der Einreichung          | Swissvotes (eigene Berechnung).   |
|               |                | bis zur Verabschiedung der bundesrätlichen Botschaft              |                                   |
|               |                | zuhanden des Parlaments                                           |                                   |
| Sammeldauer   | fr-dauer_samm  | Nur bei fakultativen Referenden: Anzahl Tage ab Beginn            | Swissvotes (eigene Berechnung).   |
|               |                | der Sammelfrist (Veröffentlichung des Parlamentsbe-               |                                   |
|               |                | schlusses) bis zur Einreichung der Unterschriften                 |                                   |
|               | fr-dauer_tot   | Nur bei fakultativen Referenden: Anzahl Tage von der              | Swissvotes (eigene Berechnung).   |
|               |                | bundesrätlichen Botschaft bis zum Tag der Volksabstim-            |                                   |
|               |                | mung.                                                             |                                   |
|               |                | Geht die Vorlage auf eine parlamentarische Initiative zurück,     |                                   |
|               |                | wird ein fehlender Wert ( . ) ausgewiesen.                        |                                   |




























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       18

## Page 1863

| Unterschriften   | unter_g     | Nur bei Volksinitiativen und fakultativen Referenden: An-        | Bundesblatt (Beschluss über das Zustandekom-   |
|                  |             | zahl gültige Unterschriften.                                     | men).                                          |
|                  |             | Bei direkten Gegenentwürfen wird die Unterschriftenzahl für      |                                                |
|                  |             | die Volksinitiative genannt, die zum Gegenentwurf geführt        |                                                |
|                  |             | hat.                                                             |                                                |
|                  |             | Sonderfälle: Gestützt auf Art. 3 der Covid-19-Verordnung         |                                                |
|                  |             | Stimmrechtsbescheinigung (Sonderregelung im Zusammen-            |                                                |
|                  |             | hang mit den Covid-Massnahmen) wurde bei den folgenden           |                                                |
|                  |             | Vorlagen jeweils nur für einen Teil der eingereichten Unter-     |                                                |
|                  |             | schriften die Bescheinigung durchgeführt: Vorlagen Nr. 644,      |                                                |
|                  |             | 645, 647, 650, 653, 654, 655, 656, 660, 661. Bei diesen Vorla-   |                                                |
|                  |             | gen unterschätzen die offiziellen Angaben also den eigentli-     |                                                |
|                  |             | chen Sammelerfolg.                                               |                                                |
|:-----------------|:------------|:-----------------------------------------------------------------|:-----------------------------------------------|
|                  | unter_u     | Nur bei Volksinitiativen und fakultativen Referenden: An-        | Bundesblatt (Beschluss über das Zustandekom-   |
|                  |             | zahl ungültige Unterschriften.                                   | men).                                          |
|                  |             | Bei direkten Gegenentwürfen wird die Unterschriftenzahl für      |                                                |
|                  |             | die Volksinitiative genannt, die zum Gegenentwurf geführt hat.   |                                                |
|                  | sammeltempo | Anzahl gesammelter gültiger Unterschriften pro einge-            |                                                |
|                  |             | setzten Sammeltag                                                |                                                |
|                  |             | Bei Initiativen: unter_g dividiert durch i-dauer_samm; bei fa-   |                                                |
|                  |             | kultativen Referenden: unter_g dividiert durch fr-dauer_samm     |                                                |
|                  |             | . Missing                                                        |                                                |
|                  |             | 0 Keine Unterschriftensammlung (obligatorische Referenden)       |                                                |
|                  |             | Sonderfälle: Gestützt auf Art. 3 der Covid-19-Verordnung         |                                                |
|                  |             | Stimmrechtsbescheinigung (Sonderregelung im Zusammen-            |                                                |
|                  |             | hang mit den Covid-Massnahmen) wurde bei den folgenden           |                                                |
|                  |             | Vorlagen jeweils nur für einen Teil der eingereichten Unter-     |                                                |
|                  |             | schriften die Bescheinigung durchgeführt: Vorlagen Nr. 644,      |                                                |
|                  |             | 645, 647, 650, 653, 654, 655, 656, 660, 661. Bei diesen Vorla-   |                                                |
|                  |             | gen war das Sammeltempo also eigentlich höher als gemäss         |                                                |
|                  |             | den verfügbaren, hier angegebenen Zahlen.                        |                                                |




























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       19

## Page 1864

|    | sparedays   | Nichtausgeschöpfte Sammelfrist: Anzahl Tage zwischen       |    |
|    |             | dem Einreichungsdatum und dem Ablauf der verfügba-         |    |
|    |             | ren Sammelfrist.                                           |    |
|    |             | dat-limit minus dat-submit                                 |    |
|    |             | . Missing                                                  |    |
|    |             | 9999 Keine Unterschriftensammlung (obl. Referenden) oder   |    |
|    |             | keine Begrenzung der Sammelfrist (Volksinitiativen, die    |    |
|    |             | vor dem 1.7.1978 lanciert wurden)                          |    |
|----|-------------|------------------------------------------------------------|----|






























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       20

## Page 1865

Abstimmungskampf

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Online-<br>Informationen<br>der Behörden | info_br-de,<br>info_br-fr,<br>info_br-en | Links zu den Online-Informationen des Bundesrats (Text-<br>dossiers, Erklärvideos, Medienkonferenzen etc.) auf<br>Deutsch, Französisch bzw. Englisch zur Abstimmungsvor-<br>lage. | Websites der Bundesbehörden.<br>Bei vergangenen Abstimmungen führen die Links zu<br>einer archivierten Version der Websites, um den Stand<br>vor der jeweiligen Abstimmung abzubilden. |
|  | info_dep-de,<br>info_dep-fr,<br>info_dep-en | Links zu den Online-Informationen des zuständigen De-<br>partements auf Deutsch, Französisch bzw. Englisch zur<br>Abstimmungsvorlage. |  |
|  | info_amt-de,<br>info_amt-fr,<br>info_amt-en | Links zu den Online-Informationen des zuständigen Bun-<br>desamts zur Abstimmungsvorlage auf Deutsch, Franzö-<br>sisch bzw. Englisch zur Abstimmungsvorlage. |  |
| Erklärvideo von<br>easyvote | easyvideo_de,<br>easyvideo_fr | Links zu den Videoclips, mit denen easyvote seit Herbst<br>2013 die Inhalte der Abstimmungsvorlagen erklärt. | easyvote (Youtube-Kanal: @easyvote). |
| Kampagnen-<br>websites | web-yes-1-de,<br>web-yes-1-fr,<br>etc.,<br>web-no-3-de,<br>web-no-3-fr | Links zu den deutsch- und französischsprachigen Kam-<br>pagnenwebsites der Komitees oder zentraler Akteur:innen<br>der Ja- und der Nein-Kampagne. Maximal 3 verschiedene<br>Websites für das Ja- und 3 für das Nein-Lager. Die Links<br>führen zu einer archivierten Version der Websites, um den<br>Stand vor der jeweiligen Abstimmung abzubilden.<br>Wenn die Rechteinhaber:innen eine Verlinkung ihrer Websites<br>auf Swissvotes ablehnen, verzichten wir darauf. Dies ist bei Eco-<br>nomiesuisse der Fall, die darauf verweist, dass ihre Kampagnen-<br>websites bei der Schweizerischen Nationalbibliothek archiviert<br>werden und vor Ort in den Räumlichkeiten der NB und ihrer<br>Partnerinstitutionen eingesehen werden können. | Kampagnenwebsites im Internet Archive<br>(https://web.archive.org/) |
| Parteiparolen,<br>Weitere Parolen | p-fdp,<br>p-sps,<br>p-svp,<br>p-mitte<br>etc. | Parolen (Stimmempfehlungen) von Parteien, Verbänden<br>und weiteren Organisationen.<br><br>1 Ja-Parole<br>2 Nein-Parole | Parolenspiegel in der Presse (erst ab 1970);<br>Bundesamt für Statistik;<br>Année Politique Suisse;<br>Websites der Parteien, Verbände und Organisati-<br>onen; |































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       21

## Page 1848

|    |    | 3 Der Akteur beschloss, keine Parole abzugeben                 | Linder et al. (2010);   |
|    |    | 4 Der Akteur empfahl, einen leeren Stimmzettel einzulegen      | Bolliger (2007);        |
|    |    | 5 Der Akteur beschloss Stimmfreigabe                           | Zürcher (2006);         |
|    |    | 8 Parole auf Bevorzugung des Gegenentwurfs (bei Stichfra-      | FDP Schweiz (1994).     |
|    |    | gen)                                                           |                         |
|    |    | 9 Parole auf Bevorzugung der Volksinitiative (bei Stichfra-    |                         |
|    |    | gen)                                                           |                         |
|    |    | 66 Neutral: keine Parole oder Empfehlung auf leer einlegen     |                         |
|    |    | oder Stimmfreigabe (nur bei Abstimmungen 1848-1969             |                         |
|    |    | verwendet)                                                     |                         |
|    |    | 9999 Organisation existiert nicht                              |                         |
|    |    | . Unbekannt                                                    |                         |
|    |    | Der Variablenname ist gebildet nach dem Schema                 |                         |
|    |    | p-[Organisationskürzel]. Aufschlüsselung der Partei-,          |                         |
|    |    | Verbands- und Organisationskürzel8:                            |                         |
|    |    | fdp Freisinnig-demokratische Partei (FDP.Die Liberalen)        |                         |
|    |    | sps Sozialdemokratische Partei                                 |                         |
|    |    | svp Schweizerische Volkspartei (bis 1936 Parolen der BGB       |                         |
|    |    | Bern)                                                          |                         |
|    |    | mitte Die Mitte                                                |                         |
|    |    | evp Evangelische Volkspartei                                   |                         |
|    |    | gps Grüne Partei der Schweiz                                   |                         |
|    |    | glp Grünliberale Partei                                        |                         |
|    |    | ucsp Christlichsoziale Partei der Schweiz (von der CVP unab-   |                         |
|    |    | hängige CSP)                                                   |                         |
|    |    | pda Partei der Arbeit                                          |                         |
|    |    | sd Schweizer Demokraten                                        |                         |
|    |    | edu Eidgenössisch-Demokratische Union                          |                         |
|    |    | fps Autopartei                                                 |                         |
|----|----|----------------------------------------------------------------|-------------------------|





























8 Hier sind grundsätzlich die aktuellen Bezeichnungen der Parteien, Verbände und Organisationen angegeben (bzw. die letzte Bezeichnung vor ihrer Auflösung). Für Namensänderungen, Abspaltungen und Fusionen der Parteien sowie Verbände im Lauf der Zeit siehe Bolliger, Christian, und Yvan Rielle (2010): Parteien und Verbände in der Schweiz. In: Linder, Wolf, Christian Bolliger und Yvan Rielle (Hg.): Handbuch der eidgenössischen Volksabstimmungen 1848–2007. Bern: Haupt. S. 691–710.
Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       22

## Page 1849

|    |    | lega Lega dei Ticinesi                                             |    |
|    |    | kvp Katholische Volkspartei                                        |    |
|    |    | mcg Mouvement Citoyens Genevois                                    |    |
|    |    | cvp Christlichdemokratische Volkspartei                            |    |
|    |    | bdp Bürgerlich-Demokratische Partei                                |    |
|    |    | lps Liberale Partei der Schweiz                                    |    |
|    |    | ldu Landesring der Unabhängigen                                    |    |
|    |    | poch Progressive Organisationen der Schweiz                        |    |
|    |    | rep Schweizerische Republikanische Bewegung                        |    |
|    |    | eco Economiesuisse (bis 15.9.2000: Schweizerischer Handels-        |    |
|    |    | und Industrieverein SHIV (Vorort))                                 |    |
|    |    | sgv Schweizerischer Gewerbeverband                                 |    |
|    |    | sbv Schweizer Bauernverband                                        |    |
|    |    | sgb Schweizerischer Gewerkschaftsbund                              |    |
|    |    | travs Travail.Suisse (bis 2002: Parolen des Christlichnationalen   |    |
|    |    | Gewerkschaftsbunds (CNG); dieser fusionierte per                   |    |
|    |    | 1.1.2003 mit der VSA zu Travail.Suisse)                            |    |
|    |    | sav Schweizerischer Arbeitgeberverband (bis 1996: Zentral-         |    |
|    |    | verband Schweizerischer Arbeitgeber-Organisationen                 |    |
|    |    | ZSAO)                                                              |    |
|    |    | vsa Vereinigung schweizerischer Angestelltenverbände               |    |
|    |    | vpod Verband des Personals öffentlicher Dienste                    |    |
|    |    | voev Verband öffentlicher Verkehr                                  |    |
|    |    | tcs Touring Club Schweiz                                           |    |
|    |    | vcs Verkehrs-Club der Schweiz                                      |    |
|    |    | acs Automobil Club der Schweiz                                     |    |
|    |    | sbk Schweizer Bischofskonferenz                                    |    |
|    |    | ssv Schweizerischer Städteverband                                  |    |
|    |    | gem Schweizerischer Gemeindeverband                                |    |
|    |    | kdk Konferenz der Kantonsregierungen                               |    |
|    |    | kkjpd Konferenz der kantonalen Justiz- und Polizeidirektoren       |    |
|    |    | gdk Schweizerische Gesundheitsdirektorenkonferenz                  |    |
|    |    | ldk Konferenz der kantonalen Landwirtschaftsdirektoren             |    |
|----|----|--------------------------------------------------------------------|----|

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       23

## Page 1850

|                 |                      | vdk Konferenz kantonaler Volkswirtschaftsdirektorinnen und      |                                                 |
|                 |                      | Volkswirtschaftsdirektoren                                      |                                                 |
|                 |                      | sodk Konferenz der kantonalen Sozialdirektorinnen und Sozial-   |                                                 |
|                 |                      | direktoren                                                      |                                                 |
|                 |                      | endk Konferenz kantonaler Energiedirektoren                     |                                                 |
|                 |                      | fdk Konferenz der kantonalen Finanzdirektorinnen und Fi-        |                                                 |
|                 |                      | nanzdirektoren                                                  |                                                 |
|                 |                      | edk Schweizerische Konferenz der kantonalen Erziehungsdi-       |                                                 |
|                 |                      | rektoren                                                        |                                                 |
|                 |                      | bpuk Schweizerische Bau-, Planungs- und Umweltdirektoren-       |                                                 |
|                 |                      | Konferenz                                                       |                                                 |
|:----------------|:---------------------|:----------------------------------------------------------------|:------------------------------------------------|
| Weitere Parolen | p-others_yes,        | Weitere Organisationen, die eine Ja-Parole fassten (auf         | Parolenspiegel in der Presse (erst ab 1970);    |
|                 | p-others_yes-fr      | Deutsch bzw. Französisch)                                       | Année Politique Suisse;                         |
|                 |                      |                                                                 | Websites der Parteien, Verbände und Organisati- |
|                 |                      |                                                                 | onen;                                           |
|                 |                      |                                                                 | Linder et al. (2010);                           |
|                 |                      |                                                                 | Bolliger (2007);                                |
|                 |                      |                                                                 | Zürcher (2006);                                 |
|                 |                      |                                                                 | FDP Schweiz (1994).                             |
| Weitere Parolen | p-others_no,         | Weitere Organisationen, die eine Nein-Parole fassten (auf       | nan                                             |
|                 | p-others_no-fr       | Deutsch bzw. Französisch)                                       |                                                 |
| Weitere Parolen | p-others_free,       | Weitere Organisationen, die eine Parole zur Stimmfreigabe       | nan                                             |
|                 | p-others_free-fr     | fassten (auf Deutsch bzw. Französisch)                          |                                                 |
| Weitere Parolen | p-others_counterp,   | Weitere Organisationen, die eine Parole zur Bevorzugung         | nan                                             |
|                 | p-others_counterp-fr | des Gegenentwurfs fassten (nur bei Stichfragen; auf             |                                                 |
|                 |                      | Deutsch bzw. Französisch)                                       |                                                 |
| Weitere Parolen | p-others_init,       | Weitere Organisationen, die eine Parole zur Bevorzugung         | nan                                             |
|                 | p-others_init-fr     | der Volksinitiative fassten (nur bei Stichfragen; auf           |                                                 |
|                 |                      | Deutsch bzw. Französisch)                                       |                                                 |
| Abweichende     | pdev-bdp_AG,         | Abweichende Parole der Kantonalsektion einer Partei bzw.        | Presseberichterstattung (erst ab 1970);         |
| Sektionen       | pdev-bdp_AI,         | eines Verbands.                                                 | Année Politique Suisse;                         |
|                 | pdev-csp_FR,         | Erfasst sind nur Fälle, bei denen die Kantonalpartei (bzw. die  | Websites der Parteien, Verbände und Organisati- |
|                 | pdev-cvp_AG,         | Kantonalsektion eines Verbands) eine von ihrer Mutterpartei     | onen;                                           |
|                 | etc.                 | (bzw. vom nationalen Verband) abweichende Parole abgegeben      | Linder et al. (2010).                           |
|                 |                      | hat:                                                            |                                                 |
|                 |                      | 1 Parteisektion beschloss abweichende Ja-Parole                 |                                                 |
|                 |                      | 2 Parteisektion beschloss abweichende Nein-Parole               |                                                 |
|                 |                      | 3 Parteisektion beschloss, keine Parole abzugeben               |                                                 |
|                 |                      | 4 Parteisektion empfahl, Stimmzettel leer einzulegen            |                                                 |
|                 |                      | 5 Parteisektion beschloss Stimmfreigabe                         |                                                 |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       24

## Page 1851

|    |    | 8 Parteisektion beschloss abweichende Parole auf Bevorzu-          |    |
|    |    | gung des Gegenentwurfs (bei Stichfragen)                           |    |
|    |    | 9 Parteisektion beschloss abweichende Parole auf Bevorzu-          |    |
|    |    | gung der Volksinitiative (bei Stichfragen)                         |    |
|    |    | [leer] Parole der Parteisektion lautete entweder gleich wie jene   |    |
|    |    | der Mutterpartei oder aber ist unbekannt                           |    |
|    |    | Der Variablenname ist gebildet nach dem Schema                     |    |
|    |    | pdev-[Organisationskürzel]_[Kantonskürzel].                        |    |
|    |    | Aufschlüsselung der Organisationskürzel siehe oben bei             |    |
|    |    | Variable p-fdp etc.                                                |    |
|    |    | Bei Frauensektionen der nationalen Parteien steht anstelle des     |    |
|    |    | Kantonskürzels “_Frauen”.                                          |    |
|    |    | Bei Jungparteien steht anstelle des Parteikürzels das Kürzel der   |    |
|    |    | Jungpartei, wobei Abweichungen der Jungpartei von ihrer natio-     |    |
|    |    | nalen Mutterpartei (nicht von der nationalen Jungpartei) erfasst   |    |
|    |    | werden:                                                            |    |
|    |    | jbdp Junge Bürgerlich-Demokratische Partei                         |    |
|    |    | jcvp Junge Christlichdemokratische Volkspartei                     |    |
|    |    | jevp Junge Evangelische Volkspartei                                |    |
|    |    | jfdp Jungfreisinnige (Jungpartei der FDP)                          |    |
|    |    | jglp Junge Grünliberale Partei                                     |    |
|    |    | jgps Junge Grüne                                                   |    |
|    |    | jlps Junge Liberale Partei                                         |    |
|    |    | jldu Junger Landesring der Unabhängigen                            |    |
|    |    | jmitte Die Junge Mitte                                             |    |
|    |    | jpda Junge Partei der Arbeit                                       |    |
|    |    | jsd Junge Schweizer Demokraten                                     |    |
|    |    | juso JungsozialistInnen (Jungpartei der SP)                        |    |
|    |    | jsvp Junge Schweizerische Volkspartei                              |    |
|    |    | Aufschlüsselung der Kantonskürzel:                                 |    |
|    |    | ZH Zürich                                                          |    |
|----|----|--------------------------------------------------------------------|----|

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       25

## Page 1852

|                |         | BE Bern                                              |                                               |
|                |         | LU Luzern                                            |                                               |
|                |         | UR Uri                                               |                                               |
|                |         | SZ Schwyz                                            |                                               |
|                |         | OW Obwalden                                          |                                               |
|                |         | NW Nidwalden                                         |                                               |
|                |         | GL Glarus                                            |                                               |
|                |         | ZG Zug                                               |                                               |
|                |         | FR Freiburg                                          |                                               |
|                |         | SO Solothurn                                         |                                               |
|                |         | BS Basel-Stadt                                       |                                               |
|                |         | BL Basel-Land                                        |                                               |
|                |         | SH Schaffhausen                                      |                                               |
|                |         | AR Appenzell Ausserrhoden                            |                                               |
|                |         | AI Appenzell Innerrhoden                             |                                               |
|                |         | SG Sankt Gallen                                      |                                               |
|                |         | GR Graubünden                                        |                                               |
|                |         | AG Aargau                                            |                                               |
|                |         | TG Thurgau                                           |                                               |
|                |         | TI Tessin                                            |                                               |
|                |         | VD Waadt                                             |                                               |
|                |         | VS Wallis                                            |                                               |
|                |         | VSo Sektion Oberwallis                               |                                               |
|                |         | VSr Sektion Valais romand                            |                                               |
|                |         | NE Neuenburg                                         |                                               |
|                |         | GE Genf                                              |                                               |
|                |         | JU Jura                                              |                                               |
|:---------------|:--------|:-----------------------------------------------------|:----------------------------------------------|
| (Detailansicht | nr-wahl | Jahr der letzten Nationalratswahl vor der Abstimmung | Parlamentsdienste der Schweizerischen Bundes- |
| Wählenden-     |         |                                                      | versammlung (online).                         |
| anteile)       |         |                                                      |                                               |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       26

## Page 1853

| (Detailansicht   | w-fdp,     | Prozentualer Wählendenanteil der jeweiligen Partei bei                | Gruner et al. 1978 (für Wahlen bis 1917);       |
| Wählenden-       | w-sps,     | der letzten Nationalratswahl vor der Abstimmung                       | Caramani 2000 (für Wahlen bis 1917);            |
| anteile)         | w-svp,     | Der Variablenname ist gebildet nach dem Schema                        | Bundesamt für Statistik (für Wahlen ab 1919).   |
|                  | w-mitte    | w-[Parteikürzel].                                                     |                                                 |
|                  | etc.       | Aufschlüsselung der Parteikürzel oben bei der Variable p-fdp etc.     |                                                 |
|                  |            | Ein Punkt (.) zeigt an, dass die Partei nicht zur letzten National-   |                                                 |
|                  |            | ratswahl antrat oder dass ihr Wählendenanteil unbekannt ist.          |                                                 |
|:-----------------|:-----------|:----------------------------------------------------------------------|:------------------------------------------------|
| (Detailansicht   | w-ubrige   | Summe der Wählendenanteile aller übrigen Parteien bei                 | Gruner et al. 1978 (für Wahlen bis 1917);       |
| Wählenden-       |            | der letzten Nationalratswahl vor der Abstimmung                       | Caramani 2000 (für Wahlen bis 1917);            |
| anteile)         |            |                                                                       | Bundesamt für Statistik (für Wahlen ab 1919).   |
| Wählendenanteil  | ja-lager   | Summe der Wählendenanteile aller Parteien, welche die                 | Swissvotes (eigene Berechnung aufgrund der      |
| des Ja-Lagers    |            | Ja-Parole ausgaben                                                    | Parteiparolen (> p-fdp etc.) und der Wählenden- |
|                  |            | Bei Stichfragen: Summe der Wählendenanteile aller Parteien,           | anteile der Parteien (> w-fdp etc.)).           |
|                  |            | welche die Parole zur Bevorzugung der Volksinitiative ausgaben        |                                                 |
| (Detailansicht   | nein-lager | Summe der Wählendenanteile aller Parteien, welche die                 | nan                                             |
| Wählenden-       |            | Nein-Parole ausgaben                                                  |                                                 |
| anteile)         |            | Bei Stichfragen: Summe der Wählendenanteile aller Parteien,           |                                                 |
|                  |            | welche die Parole zur Bevorzugung des Gegenentwurfs ausgaben          |                                                 |
| (Detailansicht   | keinepar-  | Summe der Wählendenanteile aller Parteien, welche aus-                | nan                                             |
| Wählenden-       | summe      | drücklich beschlossen, keine Parole zu fassen                         |                                                 |
| anteile)         |            |                                                                       |                                                 |
| (Detailansicht   | leer-summe | Summe der Wählendenanteile aller Parteien, welche emp-                | nan                                             |
| Wählenden-       |            | fahlen, den Stimmzettel leer einzulegen                               |                                                 |
| anteile)         |            |                                                                       |                                                 |
| (Detailansicht   | freigabe-  | Summe der Wählendenanteile aller Parteien, welche                     | nan                                             |
| Wählenden-       | summe      | Stimmfreigabe beschlossen                                             |                                                 |
| anteile)         |            |                                                                       |                                                 |
| (Detailansicht   | neutral-   | Summe der Wählendenanteile aller Parteien, welche ent-                | nan                                             |
| Wählenden-       | summe      | weder ausdrücklich keine Parole abgaben, Leereinlegen                 |                                                 |
| anteile)         |            |                                                                       |                                                 |































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       27

## Page 1848

|                 |                | empfahlen oder Stimmfreigabe beschlossen (nur 1848-                 |                                                     |
|                 |                | 1969)                                                               |                                                     |
|:----------------|:---------------|:--------------------------------------------------------------------|:----------------------------------------------------|
| (Detailansicht  | unbekannt-     | Summe der Wählendenanteile aller Parteien, deren Parole             | nan                                                 |
| Wählenden-      | summe          | unbekannt ist                                                       |                                                     |
| anteile)        |                |                                                                     |                                                     |
| Anzahl Inserate | inserate-total | Gesamtzahl aller Inserate, die in rund 50 Printmedien er-           | APS. Inseratesammlung Année Politique Suisse.       |
| in Printmedien  |                | schienen sind und im Zusammenhang mit der Abstim-                   | Année Politique Suisse, Institut für Politikwissen- |
|                 |                | mungsvorlage stehen (Summe aller Pro-Inserate, Kontra-              | schaft der Universität Bern.                        |
|                 |                | Inserate und neutralen Inserate). Der Indikator misst die           |                                                     |
|                 |                | Intensität der Inseratekampagne.                                    |                                                     |
|                 |                | Erfasst sind alle Inserate zwischen dem Montag der achten Wo-       |                                                     |
|                 |                | che vor dem Abstimmungstermin und dem Abstimmungssonntag.           |                                                     |
|                 |                | Die Zeitreihe wird seit 2013 geführt, wobei die Auswahl der er-     |                                                     |
|                 |                | fassten Printmedien über die Jahre leicht variiert. Neben den       |                                                     |
|                 |                | wichtigsten überregionalen Presseerzeugnissen wird jeweils für      |                                                     |
|                 |                | jeden Kanton mindestens eine Zeitung erfasst, wobei die Aufla-      |                                                     |
|                 |                | genstärke (gemäss WEMF) als Selektionskriterium dient. Wird         |                                                     |
|                 |                | auch die unterschiedliche Erscheinungshäufigkeit der einzelnen      |                                                     |
|                 |                | Medien (1 bis 6 Ausgaben pro Woche) berücksichtigt, ergeben         |                                                     |
|                 |                | sich zwischen 1920 und 2064 erfasste Zeitungsausgaben pro Ab-       |                                                     |
|                 |                | stimmungskampf.                                                     |                                                     |
|                 |                | Der Indikator inserate-je-ausgabe korrigiert für diese leicht vari- |                                                     |
|                 |                | ierende Anzahl erfasster Zeitungsausgaben und ist damit ein et-     |                                                     |
|                 |                | was exakteres Mass für die Intensität der Inseratekampagne.         |                                                     |
|                 | inserate-je-   | Durchschnittliche Anzahl Inserate im Zusammenhang mit               | APS. Inseratesammlung Année Politique Suisse.       |
|                 | ausgabe        | der Abstimmungsvorlage pro Zeitungsausgabe. Der Indika-             | Année Politique Suisse, Institut für Politikwissen- |
|                 |                | tor misst die Intensität der Inseratekampagne.                      | schaft der Universität Bern.                        |
|                 |                | Der Indikator korrigiert die Gesamtzahl erfasster Inserate (inse-   |                                                     |
|                 |                | rate_total) für die leicht variierende Anzahl berücksichtigter Zei- |                                                     |
|                 |                | tungsausgaben. Für Details zu den Datengrundlagen siehe inse-       |                                                     |
|                 |                | rate_total.                                                         |                                                     |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       28

## Page 1849

|            | inserate-ja   | Gesamtzahl aller Inserate, die in rund 50 Printmedien er-   | APS. Inseratesammlung Année Politique Suisse.         |
|            |               | schienen sind und für ein Ja zur Vorlage warben.            | Année Politique Suisse, Institut für Politikwissen-   |
|            |               | Für Details zu den Datengrundlagen siehe inserate_total.    | schaft der Universität Bern.                          |
|:-----------|:--------------|:------------------------------------------------------------|:------------------------------------------------------|
|            | inserate-nein | Gesamtzahl aller Inserate, die in rund 50 Printmedien er-   | APS. Inseratesammlung Année Politique Suisse.         |
|            |               | schienen sind und für ein Nein zur Vorlage warben.          | Année Politique Suisse, Institut für Politikwissen-   |
|            |               | Für Details zu den Datengrundlagen siehe inserate_total.    | schaft der Universität Bern.                          |
|            | inserate-     | Gesamtzahl aller Inserate, die in rund 50 Printmedien er-   | APS. Inseratesammlung Année Politique Suisse.         |
|            | neutral       | schienen sind und im Zusammenhang mit der Abstim-           | Année Politique Suisse, Institut für Politikwissen-   |
|            |               | mungsvorlage stehen, aber keine klare Pro- oder Kontra-     | schaft der Universität Bern.                          |
|            |               | Positionierung erkennen lassen (z.B. Ankündigungen von      |                                                       |
|            |               | Podiumsdiskussionen).                                       |                                                       |
|            |               | Für Details zu den Datengrundlagen siehe inserate_total.    |                                                       |
| Anteil Ja- | inserate-     | Prozentanteil der Inserate, die für ein Ja warben, an allen | APS. Inseratesammlung Année Politique Suisse.         |
| Inserate   | jaanteil      | Inseraten unter Ausschluss neutraler Inserate. Werte über   | Année Politique Suisse, Institut für Politikwissen-   |
|            |               | 50 bedeuten, dass mehr Ja- als Nein-Inserate geschaltet     | schaft der Universität Bern.                          |
|            |               | wurden.                                                     |                                                       |
|            |               | Für Details zu den Datengrundlagen siehe inserate_total.    |                                                       |
































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       29

## Page 1850

| Medienbericht-    | mediares-tot   | Medienresonanz der Abstimmungsvorlage: Anzahl Medien-               | fög. Abstimmungsmonitor. Online:               |
| erstattung: An-   |                | beiträge, die in den 12 Wochen vor der Abstimmung zur               | http://www.foeg.uzh.ch/de/forschung/Projekte   |
| zahl Beiträge     |                | Vorlage erschienen sind (ohne die Woche unmittelbar vor             | /Abstimmungsmonitor.html                       |
|                   |                | dem Abstimmungssonntag). Der Indikator misst die Inten-             |                                                |
|                   |                | sität der medialen Behandlung der Vorlage.                          |                                                |
|                   |                | Es wurden redaktionelle Beiträge in einer Auswahl von Mediener-     |                                                |
|                   |                | zeugnissen erfasst. Diese Auswahl wurde punktuell verändert, so-    |                                                |
|                   |                | mit sind die Zahlen nur innerhalb der jeweiligen Zeiträume direkt   |                                                |
|                   |                | vergleichbar: Abstimmungsvorlagen März 2013 bis Mai 2014: 8         |                                                |
|                   |                | Printtitel.                                                         |                                                |
|                   |                | Abstimmungsvorlagen Sept. 2014 bis Sept. 2017: 21-22 Printtitel.    |                                                |
|                   |                | Abstimmungsvorlagen März 2018 bis Juni 2018: 21 Printtitel und 5    |                                                |
|                   |                | Titel der SRG.                                                      |                                                |
|                   |                | Abstimmungsvorlagen Sept. 2018 bis heute: 14-15 Online-News-        |                                                |
|                   |                | sites, 6 Printtitel (Wochenmagazine und Sonntagszeitungen) und      |                                                |
|                   |                | 5 Titel der SRG.                                                    |                                                |
|                   |                | Für Details zum Mediensample und zum Untersuchungszeitraum          |                                                |
|                   |                | siehe die Unterlagen des fög-Abstimmungsmonitors.                   |                                                |
|:------------------|:---------------|:--------------------------------------------------------------------|:-----------------------------------------------|
|                   | mediares-d     | Medienresonanz der Abstimmungsvorlage in der Deutsch-               | fög. Abstimmungsmonitor. Online:               |
|                   |                | schweiz: Anzahl Beiträge in Deutschschweizer Medien-                | http://www.foeg.uzh.ch/de/forschung/Projekte   |
|                   |                | titeln.                                                             | /Abstimmungsmonitor.html                       |
|                   |                | Für Details zu den Datengrundlagen siehe mediares-tot.              |                                                |
|                   | mediares-f     | Medienresonanz der Abstimmungsvorlage in der Suisse                 | fög. Abstimmungsmonitor. Online:               |
|                   |                | romande: Anzahl Beiträge in Medientiteln der Suisse                 | http://www.foeg.uzh.ch/de/forschung/Projekte   |
|                   |                | romande.                                                            | /Abstimmungsmonitor.html                       |
|                   |                | Für Details zu den Datengrundlagen siehe mediares-tot.              |                                                |



























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       30

## Page 100

| Medienbericht-    | mediaton-tot    | Tonalität der Medienberichterstattung zur Abstimmungs-             | fög. Abstimmungsmonitor. Online:               |
| erstattung: To-   |                 | vorlage                                                            | http://www.foeg.uzh.ch/de/forschung/Projekte   |
| nalität           |                 | Ein positiver Wert zeigt an, dass in den Medien überwiegend be-    | /Abstimmungsmonitor.html                       |
|                   |                 | fürwortende Positionen zur Vorlage erschienen sind. Bei einem      |                                                |
|                   |                 | negativen Wert überwogen in der Medienberichterstattung die        |                                                |
|                   |                 | ablehnenden Positionen. Der Tonalitäts-Wert kann sich zwischen     |                                                |
|                   |                 | -100 (alle Medienbeiträge mit ablehnender Position) und +100       |                                                |
|                   |                 | (alle Medienbeiträge mit befürwortender Position) bewegen und      |                                                |
|                   |                 | wird folgendermassen berechnet: (Anzahl Beiträge mit positiver     |                                                |
|                   |                 | Tonalität minus Anzahl Beiträge mit negativer Tonalität) geteilt   |                                                |
|                   |                 | durch Anzahl aller Beiträge multipliziert mit 100.                 |                                                |
|                   |                 | Berücksichtigt werden Medienbeiträge, die in den 12 Wochen vor     |                                                |
|                   |                 | der Abstimmung erschienen sind (ohne die Woche unmittelbar         |                                                |
|                   |                 | vor dem Abstimmungssonntag).                                       |                                                |
|                   |                 | Für Details zu den Datengrundlagen siehe mediares-tot.             |                                                |
|:------------------|:----------------|:-------------------------------------------------------------------|:-----------------------------------------------|
|                   | mediaton-d      | Tonalität der Medienberichterstattung zur Abstimmungs-             | fög. Abstimmungsmonitor. Online:               |
|                   |                 | vorlage in Deutschschweizer Medien.                                | http://www.foeg.uzh.ch/de/forschung/Projekte   |
|                   |                 | Für Details zu den Datengrundlagen siehe mediares-tot.             | /Abstimmungsmonitor.html                       |
|                   | mediaton-f      | Tonalität der Medienberichterstattung zur Abstimmungs-             | fög. Abstimmungsmonitor. Online:               |
|                   |                 | vorlage in Medien der Suisse romande.                              | http://www.foeg.uzh.ch/de/forschung/Projekte   |
|                   |                 | Für Details zu den Datengrundlagen siehe mediares-tot.             | /Abstimmungsmonitor.html                       |
| Kampagnen-        | finanz-link-de, | Link zur Website der Eidgenössischen Finanzkontrolle mit           | EFK-Website Politikfinanzierung (online).      |
| finanzierung      | finanz-link-fr  | detaillierten Angaben zur Kampagnenfinanzierung                    |                                                |
|                   |                 | (deutsch- und französischsprachige Version).                       |                                                |
| nan               | finanz-ja-tot,  | Deklarierte Einnahmen des gesamten Ja- und des gesam-              | EFK-Website Politikfinanzierung (online).      |
|                   | finanz-nein-tot | ten Nein-Lagers in CHF, gemäss Schlussabrechnung.                  |                                                |
|                   |                 | Die Angaben beruhen auf den durch die Eidgenössische Finanz-       |                                                |
|                   |                 | kontrolle publizierten Daten. Die EFK weist ihrerseits darauf hin, |                                                |
|                   |                 | dass sie die Daten so publiziert, wie sie ihr von den offenle-     |                                                |
|                   |                 | gungspflichtigen Akteur:innen gemeldet worden sind, und dass       |                                                |
|                   |                 | letztere für die Richtigkeit der offengelegten Angaben verant-     |                                                |
|                   |                 | wortlich bleiben.                                                  |                                                |




























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       31

## Page 101

|               | finanz-ja-gr-de,     | Jeweils zwei grösste Geldgeber:innen des Ja- und des                 | EFK-Website Politikfinanzierung (online).      |
|               | finanz-ja-gr-fr,     | Nein-Lagers, gemäss Summe aus monetären und nichtmo-                 |                                                |
|               | finanz-nein-gr-de,   | netären Zuwendungen sowie Eigenmitteln in der Schluss-               |                                                |
|               | finanz-nein-gr-fr    | abrechnung. Beträge unter CHF 15'000 werden nicht aus-               |                                                |
|               |                      | gewiesen. Deutsch- und französischsprachige Version.                 |                                                |
|               |                      | Die Angaben beruhen auf den durch die Eidgenössische Finanz-         |                                                |
|               |                      | kontrolle publizierten Daten. Die EFK weist ihrerseits darauf hin,   |                                                |
|               |                      | dass sie die Daten so publiziert, wie sie ihr von den offenle-       |                                                |
|               |                      | gungspflichtigen Akteur:innen gemeldet worden sind, und dass         |                                                |
|               |                      | letztere für die Richtigkeit der offengelegten Angaben verant-       |                                                |
|               |                      | wortlich bleiben.                                                    |                                                |
|:--------------|:---------------------|:---------------------------------------------------------------------|:-----------------------------------------------|
| Kampagnen-    | poster_ja_mfg,       | Beim eMuseum.ch hinterlegte Plakate, mit denen für ein               | eMuseum / Museum für Gestaltung Zürich         |
| material Ja   | poster_nein_mfg      | Ja bzw. für ein Nein geworben wurde: Links zum eMu-                  | (www.emuseum.ch)                               |
| Kampagnen-    |                      | seum.ch, wo Bilddaten sowie Sachinformationen zum Pla-               |                                                |
| material Nein |                      | kat veröffentlicht sind.                                             |                                                |
|               |                      | Jede Verwendung der Bilddaten zugunsten Dritter - Veröffentli-       |                                                |
|               |                      | chung der Bilder oder sonstige kommerzielle Nutzung – ist ohne       |                                                |
|               |                      | die Erlaubnis der Rechteinhaber:innen nicht zulässig (siehe          |                                                |
|               |                      | https://www.emuseum.ch/rights).                                      |                                                |
| nan           | poster_ja_sa,        | Beim Sozialarchiv hinterlegte Abstimmungsmaterialien,                | Datenbank Bild+Ton des Schweizerischen Sozial- |
|               | poster_nein_sa       | mit denen für ein Ja bzw. für ein Nein geworben wurde:               | archivs (www.bild-video-ton.ch/)               |
|               |                      | Links zur Datenbank Bild+Ton des Schweizerischen Sozial-             |                                                |
|               |                      | archivs, wo Bilddaten und Sachinformationen zum Doku-                |                                                |
|               |                      | ment veröffentlicht sind.                                            |                                                |
|               |                      | Für jede Verwendung der Bilddaten sind die Nutzungsbestim-           |                                                |
|               |                      | mungen Bild+Ton des Schweizerischen Sozialarchivs zu beachten        |                                                |
|               |                      | (siehe www.sozialarchiv.ch/archiv/benutzung/nutzungsbestimmungen/).  |                                                |






























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       32

## Page 102

|     | poster_ja_bs,    | Bei der Plakatsammlung der Schule für Gestaltung Basel             | Online-Plakatsammlung der Schule für Gestal-     |
|     | poster_nein_bs   | hinterlegte Plakate, mit denen für ein Ja bzw. für ein Nein        | tung Basel (https://www.recherche-plakat-        |
|     |                  | geworben wurde: Links zur Online-Plakatsammlung, wo                | sammlungbasel.ch/objects)                        |
|     |                  | Bilddaten sowie Sachinformationen zum Plakat veröffent-            |                                                  |
|     |                  | licht sind.                                                        |                                                  |
|     |                  | Jede Verwendung der Bilddaten zugunsten Dritter - Veröffentli-     |                                                  |
|     |                  | chung der Bilder oder sonstige kommerzielle Nutzung – ist ohne     |                                                  |
|     |                  | das Einverständnis der Rechteinhaber:innen nicht zulässig (siehe   |                                                  |
|     |                  | Disclaimer unter https://www.recherche-plakatsammlungbasel.ch/).   |                                                  |
|----:|:-----------------|:-------------------------------------------------------------------|:-------------------------------------------------|
| nan | -                | Kampagnenmaterialien mit dem Vermerk «Swissvotes-Da-               | Die veröffentlichten Materialien sind Swissvotes |
|     |                  | tenbank» sind bei Swissvotes selbst hinterlegt.                    | von den folgenden Parteien und Verbänden auf     |
|     |                  | Für eine Weiterverwendung der Bilddaten – Veröffentlichung der     | Anfrage zur Verfügung gestellt worden:           |
|     |                  | Bilder oder kommerzielle Nutzung – kontaktieren Sie bitte die      | - Christlichdemokratische Volkspartei Schweiz    |
|     |                  | betreffende Partei oder den betreffenden Verband.                  | - economiesuisse                                 |
|     |                  |                                                                    | - FDP.Die Liberalen Schweiz (inkl. Material aus  |
|     |                  |                                                                    | dem Abstimmungsarchiv der FDP.DieLibera-         |
|     |                  |                                                                    | len zu überparteilichen Kampagnen)               |
|     |                  |                                                                    | - Grüne Schweiz                                  |
|     |                  |                                                                    | - Schweizer Bauernverband (SBV)                  |
|     |                  |                                                                    | - Sozialdemokratische Partei der Schweiz         |
|     |                  |                                                                    | - Travail.Suisse                                 |






























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       33

## Page 103

Abstimmungsergebnis

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Volk | volk | Volksmehr<br><br>0 Eine Mehrheit der Abstimmenden hat die Vorlage abgelehnt<br>1 Eine Mehrheit der Abstimmenden hat die Vorlage ange-<br>nommen<br>8 Bei Stichfragen: Eine Mehrheit der Abstimmenden stimmte<br>für Bevorzugung des Gegenentwurfs<br>9 Bei Stichfragen: Eine Mehrheit der Abstimmenden stimmte<br>für Bevorzugung der Volksinitiative | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
| Stände | stand | Ständemehr<br><br>0 Die Vorlage hat keine Mehrheit der Standesstimmen er-<br>reicht<br>1 Die Vorlage hat die Mehrheit der Standesstimmen erreicht<br>3 Ständemehr nicht notwendig (dies ist der Fall bei fakultati-<br>ven Referenden sowie bei Volksinitiativen in Form der all-<br>gemeinen Anregung und Volksinitiativen auf Totalrevision<br>der Bundesverfassung)<br>8 Bei Stichfragen: Eine Mehrheit der Standesstimmen gab<br>dem Gegenentwurf den Vorzug<br>9 Bei Stichfragen: Eine Mehrheit der Standesstimmen gab der<br>Volksinitiative den Vorzug | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       34

## Page 104

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Abstimmungs-<br>ergebnis | annahme | Rechtlich verbindliches Abstimmungsresultat<br><br>0 Ablehnung der Vorlage<br>1 Annahme der Vorlage<br>8 Bei Stichfragen: Gegenentwurf angenommen<br>9 Bei Stichfragen: Volksinitiative angenommen<br>. Bei Stichfragen: Ergebnis der Stichfrage obsolet, da nicht<br>gleichzeitig Volksinitiative und Gegenentwurf bei Volk und<br>Ständen eine Mehrheit erzielten | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | berecht | Anzahl Stimmberechtigter | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | stimmen | Anzahl eingelangter Stimmzettel<br>(Summe der leeren, ungültigen und gültigen Stimmzettel) | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
| Stimmbeteili-<br>gung | bet | Stimmbeteiligung<br>(eingelangte Stimmzettel im Verhältnis zur Anzahl Stimmbe-<br>rechtigter, in Prozent) | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | leer | Anzahl leer abgegebener Stimmzettel<br>(bei Initiativen mit Gegenentwurf: einschliesslich Kategorie<br>«ohne Antwort») | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | ungultig | Anzahl ungültiger Stimmzettel | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | gultig | Anzahl gültiger Stimmen<br>(entspricht der Summe der Ja- und Nein-Stimmen) | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | volkja | Anzahl Ja-Stimmen<br>Bei Stichfragen: Anzahl Stimmen für Bevorzugung der Volksini-<br>tiative | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       35

## Page 105

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  | volknein | Anzahl Nein-Stimmen<br>Bei Stichfragen: Anzahl Stimmen für Bevorzugung des Gegen-<br>entwurfs | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
| (Volk) | volkja-proz | Prozentualer Anteil der Ja-Stimmen an den gültigen<br>Stimmen<br>Bei Stichfragen: Anteil der Stimmen für Bevorzugung der Volks-<br>initiative | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
| (Stände) | kt-ja | Anzahl der annehmenden Stände (Stände mit einer Ja-<br>Stimmenmehrheit)<br>Die Kantone Appenzell Ausserrhoden, Appenzell Innerrhoden,<br>Basel-Land, Basel-Stadt, Nidwalden und Obwalden haben je-<br>weils eine halbe Standesstimme (Art. 142 der Bundesverfas-<br>sung).<br>Bei Stichfragen: Anzahl Standesstimmen für Bevorzugung der<br>Volksinitiative | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
| (Stände) | kt-nein | Anzahl der ablehnenden Stände (Stände mit einer Nein-<br>Stimmenmehrheit)<br>Die Kantone Appenzell Ausserrhoden, Appenzell Innerrhoden,<br>Basel-Land, Basel-Stadt, Nidwalden und Obwalden haben je-<br>weils eine halbe Standesstimme (Art. 142 der Bundesverfas-<br>sung).<br>Bei Stichfragen: Anzahl Standesstimmen für Bevorzugung des<br>Gegenentwurfs | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |
|  | ktjaproz | Prozentualer Anteil der annehmenden Stände<br>Bei Stichfragen: Anteil der Standesstimmen für Bevorzugung<br>der Volksinitiative | Bis 1980: Schweizerische Bundeskanzlei;<br>ab 1981: Bundesamt für Statistik. |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       36

## Page 106

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
|  | zh-berecht,<br>be-berecht<br>etc. | Anzahl Stimmberechtigter im jeweiligen Kanton<br>Der Variablenname ist gebildet nach dem Schema<br>[Kantonskürzel]-berecht<br>Aufschlüsselung der Kantonskürzel siehe oben bei Variable<br>pdev-bdp_AG etc. | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-stimmen,<br>be-stimmen<br>etc. | Anzahl eingelangter Stimmzettel im jeweiligen Kanton | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-bet,<br>be-bet<br>etc. | Stimmbeteiligung im jeweiligen Kanton<br>(eingelangte Stimmzettel im Verhältnis zur Anzahl Stimmbe-<br>rechtigter, in Prozent) | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-gultig,<br>be-gultig<br>etc. | Anzahl gültiger Stimmzettel im jeweiligen Kanton | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-ja,<br>be-ja<br>etc. | Anzahl Ja-Stimmen im jeweiligen Kanton<br>Bei Stichfragen: Anzahl Stimmen für Bevorzugung der Volksini-<br>tiative | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-nein,<br>be-nein<br>etc. | Anzahl Nein-Stimmen im jeweiligen Kanton<br>Bei Stichfragen: Anzahl Stimmen für Bevorzugung des Gegen-<br>entwurfs | Bundesamt für Statistik: STAT-TAB (online) |
|  | zh-japroz,<br>be-japroz<br>etc. | Prozentualer Anteil der Ja-Stimmen an den gültigen<br>Stimmzetteln im jeweiligen Kanton<br>Bei Stichfragen: Stimmenanteil für Bevorzugung der Volksinitia-<br>tive | Bundesamt für Statistik: STAT-TAB (online) |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       37

## Page 107

| BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| (Stände) | zh-annahme,<br>be-annahme<br>etc. | Volksmehrheit im jeweiligen Kanton (entspricht ab 1874<br>immer der Standesstimme des Kantons für das Stände-<br>mehr)<br><br>0 Nein-Mehrheit<br>1 Ja-Mehrheit<br>8 Bei Stichfragen: Mehrheit für Bevorzugung des Gegenent-<br>wurfs<br>9 Bei Stichfragen: Mehrheit für Bevorzugung der Volksinitia-<br>tive | Bundesamt für Statistik: STAT-TAB (online) |
| Ergebnisüber-<br>sicht Bundes-<br>kanzlei | bkresults-de,<br>bkresults-fr | Link zur Seite der Bundeskanzlei mit den Übersichtszah-<br>len zum Abstimmungsergebnis (deutsch- und franzö-<br>sischsprachige Version). | Schweizerische Bundeskanzlei (online) |
| Abstimmungs-<br>dashboard des<br>Bundesamts für<br>Statistik | bfsdash-de,<br>bfsdash-fr,<br>bfsdash-en | Link zum Abstimmungsdashboard des Bundesamts für<br>Statistik mit zusätzlichen Daten (deutsch-, französisch-<br>und englischsprachige Version).<br>Erst für Vorlagen ab 2023 verfügbar. | Bundesamt für Statistik: Abstimmungsdashboard<br>(online) |
| Interaktive Karte<br>des Bundesamts<br>für Statistik | bfsmap-de,<br>bfsmap-fr,<br>bfsmap-en | Link zur interaktiven Karte des Bundesamts für Statistik,<br>die die Abstimmungsergebnisse nach Gemeinden, Bezir-<br>ken und Kantonen zeigt (deutsch- und französischspra-<br>chige Version, für Vorlagen ab 2023 auch englischspra-<br>chige Version). | bis 2023: Bundesamt für Statistik: Politischer Atlas<br>(online);<br>ab 2024: Bundesamt für Statistik: Abstimmungs-<br>dashboard (online) |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       38

## Page 108

Nachbefragung

 | BEZEICHNUNG<br>IN DER ONLINE-<br>DETAILANSICHT | VARIABLE IM <br> EXCEL- <br> DATENSATZ | ERKLÄRUNG UND CODES | QUELLEN |
|-------|----------------|------------------|----------------------|
| Cockpit<br>mit Analyse-<br>ergebnissen | nach_cockpit_d,<br>nach_cockpit_f,<br>nach_cockpit_e | Link zur Seite von gfs.bern, wo ausgewählte Ergebnisse<br>der Nachbefragung in einem interaktiven Cockpit prä-<br>sentiert werden (deutsch-, französisch- bzw. englisch-<br>sprachige Version). | gfs.bern. Online: www.gfsbern.ch |































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       39

## Page 1848

Quellen der Originaldokumente von Behörden und weiterer herunterladbarer Dokumente in der Detailansicht zu jeder Abstimmungsvorlage


 |                             | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                       | ERLÄUTERUNGEN UND BEMERKUNGEN                                     |
|:----------------------------|:-----------------------------|----:|:----------------------------------------------|:------------------------------------------------------------------|
| nan                         | DETAILANSICHT BEI SWISSVOTES | nan | nan                                           | nan                                                               |
| Kurzbeschreibung Swissvotes | nan                          | nan | Abstimmungen seit 2008: Swissvotes (eigene    | PDF.                                                              |
|                             |                              |     | Erarbeitung).                                 |                                                                   |
|                             |                              |     | Abstimmungen 1848-2007: Linder et al. (2010). |                                                                   |
| Abstimmungstext             | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt.    | PDF.                                                              |
|                             |                              |     | Abstimmungen vom 12.5.1872 und vom            | Wortlaut der zur Abstimmung stehenden Vorlage.                    |
|                             |                              |     | 19.4.1874: ETH-Bibliothek Zürich,             | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn        |
|                             |                              |     | https://doi.org/10.3931/e-rara-74758 und      | von Art. 49 der Publikationsverordnung des Bundes (PublV)         |
|                             |                              |     | https://doi.org/10.3931/e-rara-26152.         | keine amtlichen Veröffentlichungen. Massgebend ist allein die     |
|                             |                              |     |                                               | Veröffentlichung durch die Bundeskanzlei.                         |
| Vorprüfung                  | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt.    | PDF.                                                              |
|                             |                              |     |                                               | Verfügung der Bundeskanzlei über die Vorprüfung von Volks-        |
|                             |                              |     |                                               | initiativen. Enthält auch die Liste der Mitglieder des Initiativ- |
|                             |                              |     |                                               | komitees.                                                         |
|                             |                              |     |                                               | Nur bei Initativen, die nach dem 1.7.1978 gestartet wurden.       |
|                             |                              |     |                                               | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn        |
|                             |                              |     |                                               | von Art. 49 der Publikationsverordnung des Bundes (PublV)         |
|                             |                              |     |                                               | keine amtlichen Veröffentlichungen. Massgebend ist allein die     |
|                             |                              |     |                                               | Veröffentlichung durch die Bundeskanzlei.                         |





























Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       40

## Page 1849

|                               | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                            | ERLÄUTERUNGEN UND BEMERKUNGEN                                 |
|:------------------------------|:-----------------------------|----:|:---------------------------------------------------|:--------------------------------------------------------------|
| nan                           | DETAILANSICHT BEI SWISSVOTES | nan | nan                                                | nan                                                           |
| Parlamentarische Initiative   | nan                          | nan | Parlamentsdienste der Schweizerischen Bun-         | PDF.                                                          |
|                               |                              |     | desversammlung (online): Geschäftsdatenbank        | Text und Begründung der parlamentarischen Initiative.         |
|                               |                              |     | Curia Vista;                                       | Nur bei Abstimmungsvorlagen, die durch eine parlamentari-     |
|                               |                              |     | Schweizerische Bundeskanzlei, Bundesblatt.         | sche Initiative initiiert wurden.                             |
|                               |                              |     |                                                    | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn    |
|                               |                              |     |                                                    | von Art. 49 der Publikationsverordnung des Bundes (PublV)     |
|                               |                              |     |                                                    | keine amtlichen Veröffentlichungen. Massgebend ist allein die |
|                               |                              |     |                                                    | Veröffentlichung durch die Bundeskanzlei.                     |
| Bericht der parlamentarischen | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt;         | PDF.                                                          |
| Kommission                    |                              |     | (in Einzelfällen: Amtliche Bulletins des National- | Bericht mit Antrag und und Erwägungen der parlamentari-       |
|                               |                              |     | rats und des Ständerats).                          | schen Kommission zur parlamentarischen Initiative.            |
|                               |                              |     |                                                    | Nur bei Abstimmungsvorlagen, die durch eine parlamentari-     |
|                               |                              |     |                                                    | sche Initiative initiiert wurden.                             |
|                               |                              |     |                                                    | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn    |
|                               |                              |     |                                                    | von Art. 49 der Publikationsverordnung des Bundes (PublV)     |
|                               |                              |     |                                                    | keine amtlichen Veröffentlichungen. Massgebend ist allein die |
|                               |                              |     |                                                    | Veröffentlichung durch die Bundeskanzlei.                     |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       41

## Page 1850

|                              | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                            | ERLÄUTERUNGEN UND BEMERKUNGEN                                   |
|:-----------------------------|:-----------------------------|----:|:---------------------------------------------------|:----------------------------------------------------------------|
| nan                          | DETAILANSICHT BEI SWISSVOTES | nan | nan                                                | nan                                                             |
| Stellungnahme des Bundesrats | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt;         | PDF.                                                            |
|                              |                              |     | (in Einzelfällen: Amtliche Bulletins des National- | Stellungnahme des Bundesrats zuhanden des Parlaments zum        |
|                              |                              |     | rats und des Ständerats).                          | Kommissionsbericht betreffend eine parlamentarische Initia-     |
|                              |                              |     |                                                    | tive.                                                           |
|                              |                              |     |                                                    | Nur bei Abstimmungsvorlagen, die durch eine parlamentari-       |
|                              |                              |     |                                                    | sche Initiative initiiert wurden.                               |
|                              |                              |     |                                                    | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn      |
|                              |                              |     |                                                    | von Art. 49 der Publikationsverordnung des Bundes (PublV)       |
|                              |                              |     |                                                    | keine amtlichen Veröffentlichungen. Massgebend ist allein die   |
|                              |                              |     |                                                    | Veröffentlichung durch die Bundeskanzlei.                       |
| Zustandekommen               | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt.         | PDF.                                                            |
|                              |                              |     |                                                    | Beschluss des Bundesrats oder der Bundeskanzlei über das        |
|                              |                              |     |                                                    | Zustandekommen (fristgerechte Einreichung der benötigten        |
|                              |                              |     |                                                    | Anzahl gültiger Unterschriften) von Volksinitiativen und fakul- |
|                              |                              |     |                                                    | tativen Referenden.                                             |
|                              |                              |     |                                                    | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn      |
|                              |                              |     |                                                    | von Art. 49 der Publikationsverordnung des Bundes (PublV)       |
|                              |                              |     |                                                    | keine amtlichen Veröffentlichungen. Massgebend ist allein die   |
|                              |                              |     |                                                    | Veröffentlichung durch die Bundeskanzlei.                       |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       42

## Page 1851

|                              | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                        | ERLÄUTERUNGEN UND BEMERKUNGEN                                 |
|:-----------------------------|:-----------------------------|----:|:-----------------------------------------------|:--------------------------------------------------------------|
| nan                          | DETAILANSICHT BEI SWISSVOTES | nan | nan                                            | nan                                                           |
| Botschaft des Bundesrats     | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt.     | PDF.                                                          |
|                              |                              |     |                                                | Empfehlungen und Erläuterungen des Bundesrats zuhanden        |
|                              |                              |     |                                                | des Parlaments.                                               |
|                              |                              |     |                                                | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn    |
|                              |                              |     |                                                | von Art. 49 der Publikationsverordnung des Bundes (PublV)     |
|                              |                              |     |                                                | keine amtlichen Veröffentlichungen. Massgebend ist allein die |
|                              |                              |     |                                                | Veröffentlichung durch die Bundeskanzlei.                     |
| Parlamentsberatung           | nan                          | nan | Amtliche Bulletins des Nationalrats und des    | PDF.                                                          |
|                              |                              |     | Ständerats.                                    | Erstmals erschienen 1891.                                     |
|                              |                              |     | Fundstelle ab 1981: Parlamentsdienste der      |                                                               |
|                              |                              |     | Schweizerischen Bundesversammlung (online).    |                                                               |
|                              |                              |     | Fundstelle vor 1981: Schweizerisches Bundesar- |                                                               |
|                              |                              |     | chiv (online).                                 |                                                               |
| Offizielles Abstimmungsbüch- | nan                          | nan | Fundstelle ab 1977: Schweizerische Bundes-     | PDF.                                                          |
| lein                         |                              |     | kanzlei.                                       | Erläuterungen und Empfehlungen des Bundesrats zuhanden        |
|                              |                              |     | Fundstelle für die Vorlagen vom 3.12.1950 und  | der Stimmberechtigten.                                        |
|                              |                              |     | vom 3.12.1972: Schweizerisches Bundesarchiv9.  | Offizielle Bezeichnung: «Erläuterungen des Bundesrates».      |
|                              |                              |     |                                                | Regelmässig erschienen ab 1977, davor lediglich in Einzelfäl- |
|                              |                              |     |                                                | len.                                                          |































9 Schweizerisches Bundesarchiv, E7113A#2001/191#407*, Az 774.100, Verhandlungen Schweiz-EG, 17.08.1972-31.12.1972.
Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       43

## Page 1852

|                               | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                       | ERLÄUTERUNGEN UND BEMERKUNGEN                                  |
|:------------------------------|:-----------------------------|----:|:----------------------------------------------|:---------------------------------------------------------------|
| nan                           | DETAILANSICHT BEI SWISSVOTES | nan | nan                                           | nan                                                            |
| Broschüre von easyvote        | nan                          | nan | easyvote, herausgegeben vom Dachverband       | PDF.                                                           |
|                               |                              |     | Schweizer Jugendparlamente.                   | Broschüre, in der easyvote vor den Abstimmungen jeweils In-    |
|                               |                              |     |                                               | halt, Pro- und Kontra-Argumente zu jeder Vorlage darlegt.      |
|                               |                              |     |                                               | easyvote, ein Partizipationsprogramm des Dachverbands          |
|                               |                              |     |                                               | Schweizerische Jugendparlamente, will mit einer einfach ver-   |
|                               |                              |     |                                               | ständlichen und politisch neutralen Informationsgrundlage      |
|                               |                              |     |                                               | das politische Interesse und die politische Partizipation ins- |
|                               |                              |     |                                               | besondere von jungen Menschen fördern.                         |
|                               |                              |     |                                               | Erstmals erschienen 2008 (auf Deutsch) bzw. 2014 (auch auf     |
|                               |                              |     |                                               | Französisch).                                                  |
| Inseratekampagne: Analyse von | nan                          | nan | Année Politique Suisse: Kampagnenforschung    | PDF.                                                           |
| APS                           |                              |     | (online).                                     | Analyse der in über 50 Printmedien erschienenen Inserate       |
|                               |                              |     |                                               | sowie (ab 2019) der redaktionellen Berichterstattung zur Ab-   |
|                               |                              |     |                                               | stimmungsvorlage.                                              |
|                               |                              |     |                                               | Erstmals erschienen 2013.                                      |
|                               |                              |     |                                               | Auf Anfrage ist bei Année Politique Suisse für Forschungs-     |
|                               |                              |     |                                               | zwecke zu jeder Abstimmungsvorlage ein PDF-Dokument er-        |
|                               |                              |     |                                               | hältlich, das alle für die Inserateanalyse erfassten Zeitungs- |
|                               |                              |     |                                               | seiten mit Inseraten enthält. Anfragen können an anja.heidel-  |
|                               |                              |     |                                               | berger@ipw.unibe.ch gerichtet werden.                          |
| Medienberichterstattung: Ana- | nan                          | nan | Forschungsinstitut Öffentlichkeit und Gesell- | PDF.                                                           |
| lyse des fög                  |                              |     | schaft der Universität Zürich (fög) (online). | Der Abstimmungsmonitor des fög wurde Anfang 2013 erst-         |
|                               |                              |     |                                               | mals lanciert und erfasst die Medienresonanz und die Tonali-   |
|                               |                              |     |                                               | tät der Beiträge im Vorfeld von eidgenössischen Volksabstim-   |
|                               |                              |     |                                               | mungen.                                                        |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       44

## Page 1853

|                       | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                          | ERLÄUTERUNGEN UND BEMERKUNGEN                                   |
|:----------------------|:-----------------------------|----:|:-------------------------------------------------|:----------------------------------------------------------------|
| nan                   | DETAILANSICHT BEI SWISSVOTES | nan | nan                                              | nan                                                             |
| Kampagnenfinanzierung | nan                          | nan | EFK-Website Politikfinanzierung (online).        | XLSX mit den Gesamteinnahmen und den Zuwendungen der            |
|                       |                              |     |                                                  | Abstimmungskampagne, jeweils Budget- und Schlussabrech-         |
|                       |                              |     |                                                  | nungs-Zahlen.                                                   |
|                       |                              |     |                                                  | Verfügbar für Abstimmungen ab dem Jahr 2024.                    |
|                       |                              |     |                                                  | Die Angaben beruhen auf den durch die Eidgenössische Fi-        |
|                       |                              |     |                                                  | nanzkontrolle (EFK) publizierten Daten. Die EFK weist ihrer-    |
|                       |                              |     |                                                  | seits darauf hin, dass sie die Daten so publiziert, wie sie ihr |
|                       |                              |     |                                                  | von den offenlegungspflichtigen Akteur:innen gemeldet wor-      |
|                       |                              |     |                                                  | den sind, und dass letztere für die Richtigkeit der offengeleg- |
|                       |                              |     |                                                  | ten Angaben verantwortlich bleiben.                             |
| Dokumente aus der     | nan                          | nan | Abstimmungen ab 2016: Argumentarien aus den      | PDF-Dokumente.                                                  |
| Abstimmungskampagne   |                              |     | Verhandlungsheften der Parlamentsdienste.        | Dokumente, die Presseartikel enthalten, dürfen wir aus urhe-    |
|                       |                              |     | Abstimmungen 1972–2015: Die Dokumente wur-       | berrechtlichen Gründen nicht zum freien Download anbieten.      |
|                       |                              |     | den von den Parlamentsdiensten des Bun-          | Gerne können Sie diese Dokumente aber in unseren Räum-          |
|                       |                              |     | desparlaments gesammelt und lagern physisch      | lichkeiten in Bern einsehen, wenn Sie sie nur für den privaten  |
|                       |                              |     | im Archiv der Parlamentsbibliothek. Für die Be-  | Eigengebrauch verwenden. Kontaktieren Sie uns dafür bitte       |
|                       |                              |     | reitstellung auf Swissvotes wurden sie digitali- | per E-Mail an info@swissvotes.ch                                |
|                       |                              |     | siert.                                           |                                                                 |
| Erwahrungsbeschluss   | nan                          | nan | Schweizerische Bundeskanzlei, Bundesblatt.       | PDF.                                                            |
|                       |                              |     |                                                  | Beschluss des Bundesrats, mit dem dieser das Abstimmungs-       |
|                       |                              |     |                                                  | resultat offiziell feststellt («erwahrt»).                      |
|                       |                              |     |                                                  | Die auf Swissvotes bereitgestellten Dokumente sind im Sinn      |
|                       |                              |     |                                                  | von Art. 49 der Publikationsverordnung des Bundes (PublV)       |
|                       |                              |     |                                                  | keine amtlichen Veröffentlichungen. Massgebend ist allein die   |
|                       |                              |     |                                                  | Veröffentlichung durch die Bundeskanzlei.                       |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       45

## Page 1848

|                              | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                           | ERLÄUTERUNGEN UND BEMERKUNGEN                                 |
|:-----------------------------|:-----------------------------|----:|:--------------------------------------------------|:--------------------------------------------------------------|
| nan                          | DETAILANSICHT BEI SWISSVOTES | nan | nan                                               | nan                                                           |
| Abstimmungsergebnis pro Kan- | nan                          | nan | Kantone ab 1848, Gemeinden und Bezirke ab         | XLSX.                                                         |
| ton, Bezirk und Gemeinde     |                              |     | 1945: Bundesamt für Statistik (online).           |                                                               |
|                              |                              |     | Bezirke 1848-1944: Linder et al. (2007).          |                                                               |
| Analysebericht Nachbefragung | nan                          | nan | 1977-2016: gfs.bern und Institute für Politikwis- | PDF.                                                          |
|                              |                              |     | senschaft der Universitäten Bern, Genf und Zü-    | Ausführlicher Bericht zu den Ergebnissen der Nachbefragung,   |
|                              |                              |     | rich.                                             | die seit 1977 im Auftrag des Bundesrats nach jeder eidgenös-  |
|                              |                              |     | 2016-2020: Voto (online).                         | sischen Abstimmung durchgeführt wird. Gegenstand der Ana-     |
|                              |                              |     | Abstimmungen ab 29.11.2020: gfs.bern.             | lyse sind die Beweggründe für die Teilnahme und für die Ent-  |
|                              |                              |     |                                                   | scheide der Stimmberechtigten.                                |
|                              |                              |     |                                                   | 1977-2016 wurden diese sogenannten VOX-Analysen durch         |
|                              |                              |     |                                                   | gfs.bern und die politikwissenschaftlichen Institute der Uni- |
|                              |                              |     |                                                   | versitäten Zürich, Genf und Bern durchgeführt.                |
|                              |                              |     |                                                   | 2016-2020 führten das FORS (Schweizer Kompetenzzentrum        |
|                              |                              |     |                                                   | Sozialwissenschaften), das ZDA (Zentrum für Demokratie        |
|                              |                              |     |                                                   | Aarau) und das Befragungsinstitut LINK das Projekt unter dem  |
|                              |                              |     |                                                   | Namen VOTO weiter.                                            |
|                              |                              |     |                                                   | Seit November 2020 laufen die Analysen wieder unter der Be-   |
|                              |                              |     |                                                   | zeichnung VOX und werden durch gfs.bern realisiert.           |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       46

## Page 1977

|                             | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                           | ERLÄUTERUNGEN UND BEMERKUNGEN                                        |
|:----------------------------|:-----------------------------|----:|:--------------------------------------------------|:---------------------------------------------------------------------|
| nan                         | DETAILANSICHT BEI SWISSVOTES | nan | nan                                               | nan                                                                  |
| Datensatz der Nachbefragung | nan                          | nan | 1977-2016: gfs.bern und Institute für Politikwis- | CSV / SAV / DTA.                                                     |
|                             |                              |     | senschaft der Universitäten Bern, Genf und Zü-    | Aus Gründen des Datenschutzes wird auf Swissvotes eine               |
|                             |                              |     | rich.                                             | leicht reduzierte Version des Datensatzes veröffentlicht. So         |
|                             |                              |     | Abstimmungen ab 29.11.2020: gfs.bern.             | enthalten die auf Swissvotes frei zugänglichen Datensätze            |
|                             |                              |     |                                                   | keine Angaben zur Wohngemeinde, zum Geburtsdatum, zur                |
|                             |                              |     |                                                   | genauen Staatsbürgerschaft bei Geburt und zur bevorzugten            |
|                             |                              |     |                                                   | Umfragesprache der Befragten. Zudem wurden für die Veröf-            |
|                             |                              |     |                                                   | fentlichung auf Swissvotes beim Geburtsjahr und der Konfes-          |
|                             |                              |     |                                                   | sion gewisse Kategorien zusammengefasst.                             |
|                             |                              |     |                                                   | Für Forschungszwecke ist unter Umständen der Zugang zu               |
|                             |                              |     |                                                   | den vollständigen Datensätzen möglich. Für alle Abstimmun-           |
|                             |                              |     |                                                   | gen ab dem 29.11.2020 können Sie sich für diesen Zweck an            |
|                             |                              |     |                                                   | gfs.bern wenden. Die Datensätze für die Abstimmungen von             |
|                             |                              |     |                                                   | 1977 bis 27.9.2020 sind bei Swissubase hinterlegt:                   |
|                             |                              |     |                                                   | https://www.swissubase.ch/de/catalogue/studies/225/19307/overview;   |
|                             |                              |     |                                                   | https://www.swissubase.ch/de/catalogue/studies/8163/15020/overview;  |
|                             |                              |     |                                                   | https://www.swissubase.ch/de/catalogue/studies/12471/13712/overview; |
|                             |                              |     |                                                   | https://www.swissubase.ch/de/catalogue/studies/13948/16830/overview. |
|                             |                              |     |                                                   | Weitere Details siehe oben zum Analysebericht Nachbefra-             |
|                             |                              |     |                                                   | gung.                                                                |
| Codebuch zur Nachbefragung  | nan                          | nan | 1977-2016: gfs.bern und Institute für Politikwis- | PDF / XLSX.                                                          |
|                             |                              |     | senschaft der Universitäten Bern, Genf und Zü-    | 1977-2016 ist das Codebuch in vielen Fällen Teil des sogenann-       |
|                             |                              |     | rich.                                             | ten Technischen Berichts.                                            |
|                             |                              |     | Abstimmungen ab 29.11.2020: gfs.bern.             | Weitere Details siehe oben zum Analysebericht Nachbefra-             |
|                             |                              |     |                                                   | gung.                                                                |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       47

## Page 1977

|                              | BEZEICHNUNG IN DER ONLINE-   |     | QUELLEN                                           | ERLÄUTERUNGEN UND BEMERKUNGEN                                |
|:-----------------------------|:-----------------------------|----:|:--------------------------------------------------|:-------------------------------------------------------------|
| nan                          | DETAILANSICHT BEI SWISSVOTES | nan | nan                                               | nan                                                          |
| Technischer Bericht          | nan                          | nan | gfs.bern und Institute für Politikwissenschaft    | PDF.                                                         |
|                              |                              |     | der Universitäten Bern, Genf und Zürich.          | Der Technische Bericht enthält namentlich Angaben zum me-    |
|                              |                              |     |                                                   | thodischen Vorgehen und zur Repräsentativität der Stich-     |
|                              |                              |     |                                                   | probe von befragten Stimmberechtigten. In vielen Fällen sind |
|                              |                              |     |                                                   | auch das Codebuch zum Datensatz und/oder der Fragebogen      |
|                              |                              |     |                                                   | der Nachbefragung im Technischen Bericht enthalten.          |
|                              |                              |     |                                                   | Nur 1977-2016 als separates Dokument erschienen. Seit 2020   |
|                              |                              |     |                                                   | sind diese Informationen jeweils im Analysebericht der Nach- |
|                              |                              |     |                                                   | befragung enthalten.                                         |
|                              |                              |     |                                                   | Weitere Details siehe oben zum Analysebericht Nachbefra-     |
|                              |                              |     |                                                   | gung.                                                        |
| Fragebogen der Nachbefragung | nan                          | nan | 1977-2016: gfs.bern und Institute für Politikwis- | PDF.                                                         |
|                              |                              |     | senschaft der Universitäten Bern, Genf und Zü-    | In vielen Fällen ist der Fragebogen im Codebuch (ab 2020)    |
|                              |                              |     | rich.                                             | oder im Technischen Bericht (1977-2016) enthalten.           |
|                              |                              |     | 2016-2020: Voto (online).                         | Weitere Details siehe oben zum Analysebericht Nachbefra-     |
|                              |                              |     | Abstimmungen ab 29.11.2020: gfs.bern.             | gung.                                                        |

































Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       48

## Page 1978

Bibliographische Angaben und Links zu den erwähnten Quellen
Année Politique Suisse. Année Politique Suisse – Dokumentation, Analyse, Diffusion. Online: www.anneepolitique.swiss.
Année Politique Suisse: Kampagnenforschung (online). Analysen der Inseratekampagnen im Vorfeld der eidgenössischen Abstimmungen. Online: https://anneepolitique.swiss/pages/campaign_research.
Bolliger, Christian (2007). Konkordanz und Konfliktlinien in der Schweiz. Parteienkooperation, Konfliktdimensionen und gesellschaftliche Polarisierungen bei den eidgenössischen Volksabstimmungen von 1945 bis 2003. Bern: Haupt.
Bundesamt für Statistik: Abstimmungsdashboard (online). Abstimmungsdashboard des BFS. Online: https://abstimmungen.admin.ch/overview.
Bundesamt für Statistik: Politischer Atlas (online). Politischer Atlas der Schweiz. Online:
   https://www.atlas.bfs.admin.ch/maps/12/map/mapIdOnly/0_de.html.
Bundesamt für Statistik: STAT-TAB (online). Interaktive Datenbank STAT-TAB. Online: https://www.pxweb.bfs.admin.ch/pxweb/de/.
Caramani, Daniele (2000). Elections in Western Europe since 1815. Basingstoke, Macmillan.
EFK-Website Politikfinanzierung (online). Politikfinanzierung. Online-Datenbank der Eidgenössischen Finanzkontrolle. Online: https://politikfinanzierung.efk.admin.ch/.
FDP Schweiz (1994). Für eine Schweiz mit Zukunft. Hundert Jahre FDP der Schweiz. Bern: Freisinnig-Demokratische Partei der Schweiz.
Forschungsinstitut Öffentlichkeit und Gesellschaft der Universität Zürich (fög) (online). Abstimmungsmonitor des fög. http://www.foeg.uzh.ch/de/forschung/Projekte/Abstimmungsmonitor.html.
Funk, Friedrich Otto (1925). Die eidgenössischen Volksabstimmungen von 1874 bis 1914. Bern: Verlag Dr. Gustav Grunau.
Gruner, Erich, et al. (1978). Die Wahlen in den Schweizerischen Nationalrat 1848-1919. Wahlrecht, Wahlsystem, Wahlbeteiligung; Verhalten von Wählern und Parteien; Wahlthemen und Wahlkämpfe 1848-1919. Bern: Francke.
Linder, Wolf, Christian Bolliger und Regula Zürcher (2007): Bezirksdaten zur Sozialstruktur und zum Stimmverhalten bei eidgenössischen Volksabstimmungen im Zeitraum 1870-2000 [Dataset]. Universität Bern. Distributed by FORS, Lausanne.
Linder, Wolf, Christian Bolliger und Yvan Rielle (2010) (Hg.): Handbuch der eidgenössischen Volksabstimmungen 1848–2007. Bern: Haupt.
Parlamentsdienste der Schweizerischen Bundesversammlung (online). Die Bundesversammlung — Das Schweizer Parlament. Online: www.parlament.ch.
Schweizerische Bundeskanzlei (online). Chronologie Volksabstimmungen. Online: https://www.bk.admin.ch/ch/d/pore/va/vab_2_2_4_1.html.
Schweizerisches Bundesarchiv (online). Online-Amtsdruckschriften. Online: https://www.amtsdruckschriften.bar.admin.ch/start.do.
Voto (online). Website des Forschungsprojekts VOTO. https://www.voto.swiss/.
Zürcher, Regula (2006). Konkordanz und Konfliktlinien in der Schweiz. Eine Überprüfung der Konkordanztheorie aufgrund qualitativer und quantitativer Analysen der eidgenössischen Volksabstimmungen von 1848 bis 1947. Bern: Haupt.
Swissvotes – ein Projekt von Année Politique Suisse, Universität Bern                       49