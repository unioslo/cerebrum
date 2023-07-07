===================================
Håndtering av språkdata i Cerebrum
===================================

.. contents:: Innholdsfortegnelse

Formålet med dette notatet er å drøfte mulighetene rundt lagring og håndtering
av språkdata i Cerebrum.



Introduksjon
=============
Cerebrum per i dag håndterer ikke språkdata i noe særlig grad. Det er kommet
ønsker fra flere hold om å støtte dette i en viss utstrekning. Noen (dog ikke
komplette) eksempler på data ønskes lagret i flere språk er:

  * Arbeidstitler til folk (typisk norsk og engelsk)
  * Navn på OU-er (alle navnetyper)
  * Konstanter i Cerebrum (f.eks. for å gi et bedre grensesnitt i
    bofhd/brukerinfo o.l. tjenester)

Potensielt sett er det dog enda flere situasjoner der språkinformasjonen kan
være nyttig, så det ville ha vært fordelaktig med en så generisk løsning som
mulig. 

Så, en overordnet liste av mål for dette prosjektet er:

  * Definere overordnet håndtering av språkdata.
  * Sette opp db-skjema for å støtte språkdata.
  * Definere API-et mot språkdata.
  * Legge inn endringene for de eksisterende API-metodene som må forholde seg
    til språkdata.

Språkdata i seg selv, gitt at vi får gode nok data fra de autoritative
systemene, må lagres i databasen. Det bør tilbys et grensesnitt som er
komfortabelt mtp språkhåndtering. Eksempelvis burde det være en mulighet til å
hente tekstdata i API-et uten en eksplisitt språkangivelse i de tilfellene der
man ikke bryr seg om språket (f.eks. fordi mottageren ikke har noe begrep om
flere språk).

Viktig skille å ha i bakhodet -- språkdefinisjonene og enkoding er relaterte
men forskjellige ting. Vi kan gjerne løse språkhåndtering på en generell basis
uten å måtte forhold oss til endringer i encoding (på kildekodenivå eller
kommunikasjonsnivå). 



Status quo
===========
La oss begynne først med en liten oversikt over hvordan språk håndteres i
dag. 

bofhd
------
Håndterer ikke språkdata. Transportlaget (klient<->bofhd) bruker unicode (det
er et krav til XMLRPC) og vil kunne håndtere data for et vilkårlig språk (blir
vanskelig å støtte thai med latin-1 encoding), men bofhd har intet
kommandobegrep for "klienten ønsker data på språket X". Således vil
f.eks. ``misc stedkode`` returnere enten alle språk eller et defaultvalg.

Database
---------
Håndterer ikke språkdata. Imidlertid var det påtenkt på et tidlig stadium. Vi
har ``language_code`` og ``ou_name_language``. Dette er forøvrig opplagte
kandidater til å basere språklagring på. Tabellene eksisterer i core-skjema,
men de er ikke i bruk.

brukerinfo
-----------
Tilbyr per i dag grensesnittet på norsk og engelsk (yay), men alle data fra
bofhd kommer uten språkmerking. Ej heller er det bakt inn språkinformasjon i
protokollen (dvs. brukerinfo (eller noen av bofhd sine klienter for den saks
skyld) har ikke mulighet til å finne ut hvilket språk data kommer på).

Kildesystemer
--------------
Tilgjengelighet av språkdata er litt variabelt kildene i mellom. FS har
f.eks. noen kolonner eksplisitt merket med språk
(``fs.sted.stednavn_bokmal``), mens UiO-SAP tilbyr en mer generisk mekanisme
der navn merkes med språkkodene::

    STED_STEDNAVN0;EN;no_val;;Research Institute for Internal
    Medicine;Research Institute for Internal Medicine;
    STED_STEDNAVN1;NO;IIF;Indremed. forsk.;Institutt for
    indremedisinsk forskning;Institutt for indremedisinsk forskning;

Per dags dato har ikke vi valgt en bevisst innstilling ift språket på diverse
dataposter. Noen steder finnes data (f.eks. i SAP-dumpen -- EN, FR, IT, NO,
osv.), andre ganger gidder vi ikke å hente dem (FS-filene, f.eks.).

Situasjonen skyldes også at språkdata ikke eksporteres ensformig fra
kildesystemene -- det er ikke opplagt hvordan man i utgangspunktet skulle
skille nynorsk fra bokmål på tvers av alle kildesystemer vi hanskes med i dag
(``nn_NO`` som kodeverdi burde ha vært et bra alternativ å velge, men vi har
begrenset påvirkningsmulighet og slikt vil antageligvis måtte legges inn i
importrutinene).

Nok en betraktning her er at noen av formatene (heldigvis våre egne) ikke kan
støtte språkangivelse slik de står::

  <sted akronym="ServTorg" forkstednavn="ServTorg" instituttnr="33" 
        stednavn="Servicetorget" stedkode_konv="10002651-0011" 
	gruppenr="11" fakultetnr="12">

Hvordan skal man bake inn språkangivelse, når datapostene er attributter og
ikke kan merkes med det? (en mulighet er å lage et nytt attributt for å kode
språket, men det vil fordre at samtlige attributter bruker det samme
språket. En annen mulighet er å dele opp dette XML-elementet, slik at de
individuelle feltene kan støtte språk).

API-et
-------
Det er overhodet ingen støtte for språkhåndtering i API-et. Videre er det også
slik at vi vil måtte utvide API-et for å håndtere dette. 

Potensielle steder i koden hvor slikt kan bli nødvendig er OU, Person,
EntityName, _CerebrumCode (evt. andre deler av Constants-rammerverket vi har).


Utfordringer
=============
Det er 4 store grupper med utfordringer som er umiddelbart opplagte: både
entiteter og ikke-entiteter trenger språkstøtte, vi må velge en felles måte å
kode språk på, vi må sørge for at de relevante datapostene leveres med språk
på samme måte fra alle kilder og vi må lage de nødvendige API-endringene slik
at det forstyrrer minst mulig.

Entiteter vs ikke-Entiteter
-----------------------------
Hovedproblemstillingen her er at vi har 2 forskjellige typer objekter (ved
mangel på bedre ord) i Cerebrum -- Entiteter og ikke-Entiteter. Hva språk
angår, så er det mest aktuelt med en løsning som behandler alle Entity-typer
likt. Det mest aktuelle er å lage et opplegg basert på å binde (ikke-unike)
navn til ``entity_id``. (Avsporing: er dette et godt tidspunkt å flytte
OU/Person-navn i dette rammeverket? Det er ingen grunn til at Person- og
stedsnavn skal håndteres forskjellig fra, si, et vilkårlig annet ikke-unikt
navn).

Blant ikke-entiteter er konstantene (la oss si alle typer) er det som er mest
aktuelt. Opplegget er omtrent det samme -- konstanten i seg selv (code), og en
bøtte med beskrivelser (code_str trenger ikke å merkes med språk -- kodebasen
er på engelsk).

Problemet er at konstantene og entitetene ikke deler en felles representasjon:
den magiske id-en til hver "gruppe" tappes fra egen sekvens (``code_seq`` og
``entity_id_seq``). Trist, synd, leit (nok en avsporing: hvorfor er det 2
sekvenser, egentlig?)

Språkkoding
------------
  * Representasjon av språk via konstanter.
  * Abstraksjonsmekanismer som tilbyr samme grensesnitt på tross av
    forskjellige kilder (f.eks. skal vi lage XML med data der noen av postene
    har språkinfo med seg, bør dette gjøres likt på tvers av kildesystemer)
  * Felles platform der alle kildesystemene kan tvinges inn.

API-endringene
---------------
  * Prøve å holde endringene til et minimum for å knekke minst mulig kode av
    gangen. 
  * Tilby en mulighet for å hente data der språk er tilgjengelige uten å bry
    seg om språk (f.eks. kan det tenkes at det ikke spiller en rolle for en
    jobb hvilket språk OU-navnet er på, all den tid det finnes bare ett navn
    fra det aktuelle autoritative kildesystemet). 
  * Defaultspråk med et oppplegg à la SYSTEM_LOOKUP_ORDER? (Dvs. der API-et
    maskerer at det er flere språk for et ``get_name(name_type)``-kall).
  * Utvide konstantrammeverket til å støtte beskrivelser på forskjellige
    språk.
  * Legge inn støtte for språk i bofhd. Det kan gjøres på flere måter:

      + Bare dumpe alle språkdata av en bestemt type for en gitt kommando (si
        alle OU-ens navn på alle språk) og la klienten finne ut av hva som
        trenges. Minimalt med endringer for bofhd, antageligvis en del
        endringer for jbofh/brukerinfo.
      + Ha et standardopplegg (forutsatt at API-et støtter slikt) men samtidig
        tilby en egen kommando for å hente entitetsnavn av en gitt type på et
        gitt språk. Minimalt med endringer for jbofh, en del pes for
        brukerinfo (ikke minst hardkodingen av alle konstantene). 
      + Ha et opplegg der klienten kan registrere "sitt" språk ved pålogging
        og bofhd tar hensyn til det (evt. faller tilbake på et standardvalg
        når det aktuelle språket ikke lenger er tilgjengelig) på alle
        kommandoer som returnerer data med språkinfo. Blir potensielt ganske
        pes for bofhd, dog herlig simpelt for jbofh/brukerinfo (de gjør ett
        ekstra kall for å sette språk etter pålogging).
      + Feilmeldingene fra bofhd burde man gjøre noe med. gettext? Noe annet? 
        La CerebrumError finne ut av dette selv?
  * Uniform tilgang til språkdata uansett om det skjer fra Constants eller
    Entity. Dvs. fra Python skal uthenting av språknavn se likt ut.



Forslag
========
Det er flere deler som kan angripes litt uavhengig av hverandre.


Kildedata
----------
Iallfall følgende kildesystemer leverer data med språkinformasjon SAP-UiO,
SAP-SSØ, FS, ABC-Enterprise. Hver av disse har sin egen måte å representere
språk på. Ideelt sett burde man ha et felles filformat, men det skjer nok
ikke, så det er bare å justere importrutinene.

Hver importjobb trenger å bry seg kun om sine egne inputverdier. Dvs. vi kan
leve med at hvert system koder språk på forskjellige måter. MEN, hver
importjobb vil måtte oversette fra systemspesifikke språkkoder til Cerebrum
sine. 

FIXME: Et lite problem her -- hva med de jobbene som henter data fra filene
direkte framfor å slå opp i Cerebrum? *Hvis* slike jobber håndterer noe som
ligner på språkdata, må de skrives om (fortrinnvis for å hente data fra
Cerebrum). 

FIXME: Hvilke jobber er det?


DB-skjema
----------
Vi kan gjenbruke den eksisterende tabellen for språkkonstanter::

    language_code(code, code_str, description)
                  <-->

Da kan man ganske greit referere til språk fra koden slik vi bruker
konstantene ellers::

    123	    nn		Nynorsk
    124	    nb		Bokmål
    125	    en		English
    126	    fr		Français
    127	    de		Deutsch

En liten notis angående code_str --
<http://en.wikipedia.org/wiki/Language_codes> har en del å velge fra. Vi
trenger f.eks. å skille mellom bokmål og nynorsk (nb, nn), men hvilken av
disse mulige kodinger av språk skal man velge for code_str? (den skal være
entydig og ikke være funnet opp av oss, men heller standarisert). Det er nok
ingen grunn å droppe description (kjekt for mennesker), hverken for
``language_code`` eller andre konstantene. Den kolonnen kan gjerne inneholde
noe mennesker kan forholde seg til og kan brukes når folk ikke bryr seg om
språk (for språkkonstantene kan man velge språknavnet på det aktuelle
språket. For andre konstanter kan vi f.eks. putte noe på engelsk (eller norsk,
dersom det gir mer mening)).

Så, til navnlagringen i seg selv. Først for konstantene::

    constant_language(code, language, value)
                      <------------->

der ``language`` er en foreign key til ``language\_code.code``::

    984		 123   	       Arbeidstittel
    984		 124	       Arbeidstittel
    984		 125	       Work title

(En kuriøsitet -- språkkonstantene i seg selv vil kunne legge i
``constant_language``, slik at man kan merke bokmål som både "bokmål" og
"Norwegian", f.eks.).

Nå til entitetene. Man trenger iallfall ``entity_id``, ``language`` og
``value``. Spørsmålet er om det er tilstrekkelig. Er det aktuelt å tillate at
den samme entiteten (si Person) har den samme navnetypen (si arbeidstittel)
representert på forskjellige måter på samme språk (!) fra forskjellige
kildesystemer? La oss se på den enkleste varianten først::

  entity_name_language(entity_id, name_type, language, source_system, value)
                       <------------------------------------------->

Dette vil gi oss mulighet til å registrere arbeidstitler, akronymer,
forskjellige stedsnavn osv med et språk. PK-en er vel også den minste mulige,
gitt nåværende problemstillinger.

En åpen problemstilling er hvorvidt vi ønsker en prioritering av
navneinformasjon. Eller registrering av kildesystemet. Det er intet
umiddelbart behov for prioritering. Siden de forskjellige systemene gir
ikke-overlappende navnetyper (iallfall enn så lenge), er det muligens ikke
behov for ``source_system`` heller?

Sist, men ikke minst, hva gjør vi med dagens språkinformasjon som ligger i
Person og i OU? (OU har jo ikke færre enn name, acronym, short_name,
display_name og sort_name definert i ou_info-tabellen. person_name-tabellen
har antageligvis en bøtte med navn der språk ikke er så viktig (som
f.eks. for- og etternavn, men samtidig plasserer man ting dit som helt klart
kan være forskjellige på forskjellige språk (arbeidstittel)).

Legg merke til at ``value`` ikke har en unique constraint på seg --
``entity_name`` er per i dag den tabellen som bærer på unike navn (brukernavn
og slikt). Apropos det, burde den omdøpes til ``entity_unique_name``?


API-endringene
---------------
Dette er antageligvis den mest åpne problemstillingene, siden målene er såpass
motstridende. 

La oss begynne med konstantene først, siden man har mindre gammel kode å
forholde seg til::

  class ConstantName(object):
      table = "[:table schema=cerebrum name=constant_language]"

      def get_name_language(self, language=None):
          if language is None:
	      return str(self) # <- fetches 'description'

	  return "SELECT ... FROM contant_language"
      # end

      def update_name_language(self, *rest):
          for (name, language) in rest:
              <insert or update>

      def delete(self):
          <delete from constant_language where ...>
  # end ConstantName


  class Constants(..., ConstantName):
      # ...

Kunne noe slikt være et utgangspunkt? Det som er teit er at get_name_language
vil returnere en liste. Kanskje man kan omskrive den til å returnere
description (``str(self)``) når det aktuelle språket ikke er tilgjengelig?
Mulig man ønsker en eller annen ``list_*``-variant også. 

Nå, til entitetene. Vi har allerede en mal i form av ``EntityName``:

  * delete()
  * get_name(domain)
  * get_names()
  * add_entity_name()
  * delete_entity_name()
  * update_entity_name()
  * find_by_name()
  * list_names()

Ser man også på Person, har klassen følgende grensesnitt mot navn:

  * en del metoder for å manipulere navn gjennom ``populate``
    affect_names, populate_name, write_db
  * en del spesiallogikk for ``system_cached``
  * get_name
  * get_names
  * getdict_persons_names
  * search

Det kompliserte her er det er ``populate``-logikk og den må samsvare med
dataene i databasen. I tillegg er det selvsagt slik at hvis vi skal lagre noe
av informasjonen i ``person_name`` (for- og etternavn, f.eks.), vil det
virke forvirrende om andre navn (eksempelvis ``work_title``) skal plasseres i
en annen tabell og skal behandles på en annen måte.

Sist men ikke minst har vi OU-klassen. Her er alle navn satt opp som
objektattributter (``__write_attr__``), som er atter en ny variant av
navnhåndtering. Metodene som er innblandet i navnhåndtering:

  * populate
  * write_db
  * new
  * get_names
  * get_acronyms
  * search

Det er egentlig litt trist at vi har så mange parallelle måter å håndtere navn
på. Det burde være to, maks -- en for unike og en for ikke-unike navn. 

Før man begynner med kreative forslag på navnhåndtering for Entity-instanser,
la oss først se på hvordan navnedata fordeler seg i Cerebrum i dag::

  => select pnc.code_str, count(pn.*) 
     from person_name pn, person_name_code pnc 
     where pnc.code = pn.name_variant group by code_str ;
     code_str    | count  
  ---------------+--------
   FIRST         | 474913
   WORKTITLE     |  13204
   PERSONALTITLE |    933
   LAST          | 474913
   FULL          | 199185

  => select vdc.code_str, count(en.*) 
     from entity_name en, value_domain_code vdc 
     where vdc.code = en.value_domain group by code_str, value_domain ;
     code_str    | count  
  ---------------+--------
   dns_owner_ns  |  49496
   group_names   | 266386
   account_names | 199747
   host_names    |    173

Innholdet av ``entity_name`` er uten noe tilknytning til språk og det er ikke
naturlig å sette inn språk der mtp. hva slags data er lagret ("språket" til
brukernavn er ikke spesielt nyttig/interessant).

``person_name`` og ``ou_info`` bør nok revideres (det er et reelt behov for
det allerede i dag), men, hvordan håndterer man personnavn (altså, ekte navn
som folk har) ift titler og den slags som vi bruker person_name til?

En mulighet (ressurskrevende) er å lage generell støtte for ikke-unike navn og
lempe alt dit. Det vil kunne brukes til OU-er, Personer, e-postadresser --
alt. Det vil fremdeles være nødvendig med 3 tabeller:

   * entity_name -- unike navn uten språk
   * entity_non_unique_name -- ikke-unike navn uten språk
   * entity_name_language -- ikke-unike navn med språkdata

Da kan vi bli kvitt person_name, trimme ou_info og åpne for lagring av navn
med og uten språk. Høres fint ut, men det er en enorm innsats å dra OU+Person
over på det skjema.

En annen mulighet er å organisere ting slik:

   * entity_name -- unike navn uten språk.
   * person_name -- (ekte) personnavn uten språk
   * entity_name_language -- ikke-unike navn med språkdata.

Her beholder vi ``person_name``, trimmer ``ou_info`` og støtter (ikke-unike)
navn med språk. Den soleklare ulempen er at navnhåndtering i Person blir
ulidelig komplisert.

Nok en variasjon over tema er å la ``ou_info`` og ``person_name`` forbli
uberørt, men samtidig lage ``entity_name_language`` med et passende
grensesnitt. Det grensesnittet i sin tur kan brukes for å håndtere
flerspråkdata. Dersom metodene har ikke-overlappende navn, kan vi introdusere
flerspråkstøtte gradvis (dvs. gradvis fase ut person/OU-spesifikke
navnehacks). Ulempen er at navneinformasjon blir atter mer komplisert (det
siste vi vil akkurat nå er mer kode for marginalt mer funksjonalitet). 

Jeg vet ærlig talt ikke hva som er den lavest hengende frukten her. 

Hvis vi skal ha ``EntityNameLanguage``, så kan muligens det 1. utkastet se
slik ut::

   class EntityNameLanguage(object):

       def update_name_language(self, *rest):
           for name, language, source in rest:
               <insert or update>
               
       def get_name_language(self, languages=..., source=..., name_type=...)
           # find 1 row matching...

       def search_name_language(self, ...):
           # find multiple rows matching...

       def delete_name_language(self, <primary key attributes>):
           # delete from entity_name_language where ...

Så kan man stappe en slik mixin inn i enhver klasse som arver fra ``Entity``. 

En liten avsporting -- jeg har aldri likt populate-ideen for navn: logikken i
``write_db`` blir en del mer komplisert, man må fremdeles hente ut navn for å
finne ut om man skal gjøre en update eller en insert og evt. hvor mange
deletes som skal følge med og mellom populate og write_db er ikke uthenting av
navn mulig på konsistent vis (API-et tar ikke hensyn til data cachet internt,
så populate(), get_name*, write_db() vil gi et annet svar enn populate(),
write_db(), get_name*). Derfor er ``populate()``-aktig logikk utelatt fra
``EntityNameLanguage``.


Implementasjonsplan
====================
Isjda, hvilken ende begynner man i?

Det som brenner mest er navn på OU-er på ymse språk, så fokuset bør ligge
der. ``EntityNameLanguage`` kan innføres uten stor dramatikk. Skal man droppe
name/short_name/acronym osv tilgjengelige direkte som attributter? Kan iofs
erstatte dem med properties, slik at klientkoden kan fortsette å bruke
``ou.acronym`` som en slags "default/fallback" verdi, mens for de tilfellene
der det er viktig å være klar over språket, bruker man det som
``EntityNameLanguge`` tilbyr?

En slik tilpasning vil forresten gi oss anledning til å gradvis migrere koden
(en stor gulrot i seg selv). Dog, mulig implementasjon gjennom properties vil
ha ganske høye kostander (hvis koden refererer til ``ou.name`` ukritisk, kan
det tenkes at å ta en "select * from ..." på hver property-oppslag vil bære
betydelige kostnader).

Hva arbeidstitler på personer angår, vet jeg ikke helt hvordan man skal
angripe uten store endringer i kodebasen.


Bakoverkompatibilitet
======================
Det er nok et problem å ta hensyn til. Navn (Person, OU, Entity) står sentralt
i Cerebrum, og vi kan ikke foreta endringer av denne størrelsen uten å berøre
andres kodetrær. Hvordan avklares dette med NTNU og Tromsø?
