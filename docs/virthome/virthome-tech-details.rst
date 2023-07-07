=========
VirtHome 
=========

.. contents:: Innholdsfortegnelse



Innledning
============
Dette dokumentet beskriver de tekniske detaljene p� Cerebrum-siden knyttet til
implementasjonen av VirtHome-funksjonalitet.

Hovedf�ringen for implementasjonen er � gjenbruke s� mye av Cerebrum-kodebasen
som overhodet mulig. Der hvor databaseskjema ikke tilbyr de n�dvendige
skrankene, velger vi heller � flytte h�ndteringen av skrankene inn i koden,
heller en � lage nye moduler.



VirtHome-entiteter
===================
Det er tre logiske enheter som utpeker seg som entiteter i VirtHome -- brukere
uten f�derert tilknytning (VirtAccount), brukere med f�derert tilknytning
(FEDAccount) og grupper (VirtGroup) der de to f�rste entitetene kan v�re
medlemmer. Alle de andre entitetene vi trenger er allerede i Cerebrum-kjernen.

VirtAccounts (VA) er brukere som vi vet minst om, da all informasjon om disse
kommer fra en ikke tiltrodd kilde (det er meningen av folk skal kunne lage
sine egne VirtAccounts uten noe form for verifikasjon av opplysningene). Den
eneste "merkelappen" vi har p� disse er e-postadressen.

FEDAccounts (FA) er brukere som stammer fra en tilknyttet institusjon og disse
besitter bl.a. en ID i Feide og antas videre til � v�re verifiserte (dvs. vi
antar at informasjonen lagret i VirtHome om disse brukere er til � stole p�).

VirtGroups (VG) er grupper der begge typer konti kan v�re medlemmer (og gjerne
innen den samme gruppen).

Det er intet poeng i � finne p� nye entiteter i db-skjema, og f�lgelig lagrer
vi informasjon om begge typer konti i ``code_tables.sql:account_info``, og
informasjon om grupper legges i ``core_tables.sql:group_info``. 


VirtAccount
------------
Selv om vi gjenbruker ``account_info``, m� det til en ny entitet i kodebasen
for � st�tte visse operasjoner p� VirtAccounts. Koden for VirtHome kontotyper
ligger i ``Cerebrum/modules/virthome/VirtAccount.py``. VirtAccount blir
naturlig til egen klasse, ``VirtAccount``. B�de ``VirtAccount`` og
``FEDAccount`` (se under) har noen fellestrekk og fellesbaseklassen for disse
arver fra Account. Ideelt sett burde dette ha blitt l�st ved � la
``AccountType``, ``AccountHome`` og autentiseringsfunksjonaliteten v�re
separate mixin-klasser som legges i ``CLASS_ACCOUNT`` ved behov, men det er
dessverre ikke slik. Pga. litt uheldig arverekkef�lge til ``Account`` m� man
reimplementere en del metoder vi kunne ellers ha greid oss uten. Disse kaster
``NotImplementedError`` dersom de blir brukt (det er ikke meningen at de skal
kunne brukes). 

.. FIXME: Kan vi l�se dette mer elegant med metaklasser?

For hver VirtAccount lagrer vi f�lgende data i Cerebrum:

  * E-postadresse (p�krevd, ikke unik). Denne lagres som egen
    ``contact_info``. Det er ikke noe poeng i � dra inn ``Email``-modulen kun
    for � lagre adressene. 
  * Brukernavn (p�krevd, unik) lagres som egen type ``entity_name``.
  * Opprettelsesdato (p�krevd), lagres i ``account_info``
  * Sluttdato (p�krevd), lagres i ``account_info``. DB-skjema har ikke
    NOT NULL skranken p� sluttdato, s� dette vil m�tte forsikres i koden.
  * Navn p� eieren. Denne er valgfri. Et praktisk problem her er at
    ``entity_name`` har en unique-skranke p� navn av samme type og kan derfor
    ikke brukes til � lagre eiernavn. Det greieste er � lagre dette som
    entity_contact_info. Ideelt sett burde vi migrere Cerebrum til � bruke
    unike og ikkeunike navn og ha dertil egnede tabeller i db-skjema. Dette
    l�ses dog ikke av/i VH.
  * Passord. Denne kan lagres i ``account_authentication`` og
    ``password_history``. 
  * Spread til LDAP (og sikkert en del andre). Dette l�ses enkelt
    vha. ``entity_spread``. 
  * Karantener. Dette l�ses enkelt vha. ``entity_quarantine``.
  * Traits (litt uklart hvilke traits vi kan trenge akkurat n�, men det
    spiller liten rolle) -- EntityTrait-modulen er veltestet.

Siden vi ikke kan stole p� navn som folk skriver selv om seg selv, m� vi ha et
system for � merke alle navn p� VA-eiere slik at det fremg�r tydelig at
informasjonen ikke er fra en tiltrodd kilde. Merk at dette gjelder kun
eksporten til andre systemer (slik som LDAP). Dvs. at "Schnappi das Krokodil"
vil m�tte merkes p� en eller annen m�te som tydeliggj�r at det navnet ikke
stammer fra en tiltrodd kilde, slik som f.eks. "Schnappi das Krokodil
(unverified)" **kun** ved eksport til andre systemer; internt i Cerebrum
forblir navnet uendret (internt i Cerebrum vet man til enhver tid ut fra
kontotypen om informasjonen om kontoen er fra en tiltrodd kilde).

Videre er det slik at ``account_info`` alltid har en eier, som er enten en
account eller en gruppe. Siden vi ikke har en entitet i Cerebrum som eier en
VirtAccount, er det naturlig � la "systemet" eie VAs. I dette tilfellet blir
det ``cereconf.INITIAL_GROUPNAME/INITIAL_ACCOUNTNAME`` som eier alle VAs.

Navn p� VAs (egentlig p� b�de VA og FA) i VirtHome har en indre struktur --
"<name>@<realm>". For VirtAccount spesifikt er <realm> fastsatt
(``cereconf.VIRTHOME_REALM`` inneholder realm) -- alle VA-brukernavn er p�
formen "<noe>@VH". "<noe>"-delen er opptil hver enkel bruker � bestemme,
s�fremt det resulterende brukernavnet ikke er allerede tatt.
``VirtAccount:illegal_name()`` sjekker at det blir h�ndtert (vi har ingen
db-skjemaskranker p� dette punktet).

Et vesentlig punkt knyttet til alle VA-er er at en rekke kommandoer (ogs�
opprettelse) krever et bekreftelsessteg. Dette er beskrevet senere i
`Bofhd-kommunikasjon`_. 

Det er litt uklart om VA m� kunne slettes komplett fra Cerebrum, dvs. om vi
trenger en passende ``nuke()``-funksjon. Imidlertid VA-er som ikke er
bekreftet (se avsnittet om opprettelse) m� kunne slettes. Relatert til dette,
``is_active()`` for en VA m� ta hensyn til expire_date OG til hvorvidt kontoen
er blitt bekreftet.

En VA opprettes med en gang i VH, etter at brukeren ba om opprettelse av en ny
VA, men settes med en gang i karantene, slik at nye brukere er n�dt til �
bekrefte opprettelsen f�r kontoen tas i bruk. I det en slik bekreftelse
kommer, fjernes karantenen og VA gis spread til LDAP.

For VA tar Cerebrum vare p� passord. Vi trenger � definere hva et gyldig
passord er og sjekket det i API-et (``PasswordChecker``-rammeverket er p�
plass alt). Siden Cerebrum har oversikt over passord, kan vi autentisere
VA-brukere ved innlogging gjennom bofhd/cerebrum.

For selve passordkravet er det enkleste � legge seg p� passphrases. Vi krever
at passordet tilfredstiller samtlige av f�lgende krav:

  - Minst 12 tegn.
  - Ingen repetisjon p� 4 eller flere tegn. ('aaaa' -- ikke tillatt)
  - Ingen sekvenser p� 4 tegn eller lengre ('1234' og 'qwerty' -- ikke
    tillatt)
  - Passord er fra alfabetet [a-zA-Z0-9] + et par spesialtegn.

.. FIXME det er potensielt aktuelt � tillate kortere passord, MEN da m� vi har
   mer strikte sjekker n�r passordene er i 8-12 tegn i lengde.

Vi krever opprettelses- og expire-dato for alle VA-er. DB-skjema st�tter ikke
dette kravet, s� dette m� sjekkes i API-et. I utgangspunktet antar vi at en
konto er ekspirert etter ett �r. Uansett er expire_date aldri NULL/None.

For � logge seg inn i VirtHome skal folk bruke brukernavn. E-post, derimot, er
den kommunikasjonskanalen som VH har til hver enkel bruker (det er i praksis
den eneste m�ten systemet kan kommunisere med brukeren p�).

Hver VA blir n�dt til � bekrefte at kontoen er i bruk med jevne mellomrom. Det
enkleste er � gj�re dette ifm. passordbytte som skjer hver 6. m�ned. Som et
ledd i oppryddingsrutinene, vil man sende rutinemessige varsler om
passordbytte (ikke ulik slik det gj�re ved UiO i dag). Det er forel�pig uklart
hva som skjer med VA, dersom brukeren unnlater � bytte passordet (VA skal f�
karantene og skal sperres fra eksport til eksterne systemer (f.eks. LDAP), men
skal vi slette brukeren helt? Gj�re noe annet?)

Et annet �pent sp�rsm�l er hvordan selve passordbytte skal forl�pe seg. Vi m�
hindre at uvedkommende DoS-er en VA, samtidig som det skal v�re mulig, etter �
ha glemt et passord, � f� gjenopprettet tilgangen til kontoen.



FEDAccount
-----------
Det er en del felles trekk mellom FA og VA, s� de begge bruker
``account_info`` og arver fra samme baseklasse. Likevel er det noen
forskjeller, slik at hver av disse f�r egen klasse.

For hver FEDAccount lagrer vi f�lgende data i Cerebrum:

  * E-postadresse (p�krevd, ikke unik). Denne lagres som egen
    ``contact_info``. Det er ikke noe poeng i � dra inn ``Email``-modulen kun
    for � lagre adressene. 
  * Brukernavn (p�krevd, unik) lagres som egen type ``entity_name``.
  * Opprettelsesdato (p�krevd), lagres i ``account_info``
  * Sluttdato (p�krevd), lagres i ``account_info``. DB-skjema har ikke
    NOT NULL skranken p� sluttdato, s� dette vil m�tte forsikres i koden.
  * Navn p� eieren. Denne er valgfri. Et praktisk problem her er at
    ``entity_name`` har en unique-skranke p� navn av samme type. I dette
    tilfellet blir vi n�dt til � utvide skjema med en ny tabell for � lagre
    ikke-unike navn av bestemt type -- ``entity_non_unique_name``.
  * Spread til LDAP (og sikkert en del andre). Dette l�ses enkelt
    vha. ``entity_spread``. 
  * Karantener. Dette l�ses enkelt vha. ``entity_quarantine``.
  * Traits (litt uklart hvilken traits vi kan trenge akkurat n�, men det
    spiller liten rolle) -- EntityTrait-modulen er veltestet.

Da data for FA antas til � stamme fra en tiltrodd kilde, gj�res det ingen
manipulasjoner med eiernavn for FA-er ved eksport til eksterne systemer slik
det gj�res med VA. Videre er det ogs� slik at siden denne tiltrodde kilden er
autoritativ for informasjonen om en FA, oppdateres data om FA-en i VH hver
gang vedkommende logger seg inn i VH (slik at vi f.eks. automatisk oppdaterer
eiernavnet for kontoen, dersom navnet endrer seg i Feide).

I likhet med VA-er, eies FA-er av systemet
(``cereconf.INITIAL_GROUPNAME/ACCOUNTNAME``).

I likhet med VA-er, er navn p� FA-ene strukturert som
``<name>@<realm>``. Imidlertid f�r hver tilknyttet institusjon egen "<realm>"
(dette sjekkes i API-et, siden db-skjema ikke har den type sjekke innebygd).

En viktig forskjell mellom VA og FA er autentisering. VirtHome lagrer ikke
passord for FA-ene -- disse skal autentiseres eksternt, heller enn gjennom
Cerebrum. Dette reiser en del andre problemstillingene, siden f.eks. bofhd
(som er (om enn i en modifisert utgave og bak en web-applikasjon) det
verkt�yet vi skal bruke for � tilby et grensesnitt til brukere) alltid har
gjort autentiseringen selv. Mer om dette i `Innlogging`_. API-et b�r har en
sperre for � sette passord p� FA-ene.

I likhet med FA f�r VA-brukere LDAP-spread etter f�rste innlogging.

N�r det gjelder expire-dato, er det en utfordring knyttet til FA-er, siden de
ikke har noe "bytt-passord-i-VH"-funksjon som man kan bruke som bekreftelse p�
at kontoen fremdeles er i bruk. Det enkleste er � sende ut bekreftelsese-post
(ikke ulik passordvarsling) og be brukeren bekrefte bruken ved � f�lge en
link.

Siden FA og VA deler den samme tabellen (``account_info``), og vi trenger �
skille mellom disse to typene, introduseres et par nye konstanter (for �
skille p� ``account_info.np_type``) -- ``virtaccount_type`` og
``fedaccount_type``.


VirtGroup
----------
Den tredje og siste VirtHome-entiteten er VirtGroup -- en gruppe der
medlemmene er VA-er og FA-er. VG er ganske like gruppene i Cerebrum.

Alle VG-er har en eier, en creator og fra 0 til flere moderatorer. Det er kun
FA-er som kan v�re eier/creator/moderator; VA-er kan kun v�re medlemmer.

For hver VirtGroup lagrer vi f�lgende data i Cerebrum:

  * Gruppenavn (p�krevd) lagres i ``entity_name``.
  * Gruppebeskrivelse (p�krevd) lagres i ``group_info``.
  * Eier (p�krevd) lagres i bofhd_auth*. At eieren er p�krevd sikres via
    bofhd.
  * Moderatorne for gruppen (valgfri), lagres i bofhd_auth*. 
  * Spreads lagres i ``entity_spread`` (f.eks. spread til LDAP).
  * En gruppe"ressurs" (URL, forel�pig) som er ment til � peke p�
    ekistensgrunnlaget for gruppen. F.eks. hvis gruppen representerer hvem som
    skal f� lov til � kommentere p� en spesiell blogg, s� er ressursen URL til
    denne bloggen. Dette lagres som ``entity_contact_info``.

.. FIXME: Muligens "display name" av noe slag, alts� framvisningsnavn, dersom
   gruppenavn er laget for datamaskiner heller enn mennesker. Det er blitt
   foresl�tt � lage gruppenavn p� formen "urn:mace:uio.no:...", men dette er
   ikke spesielt menneskevennlig.

.. FIXME: Kanskje modereringsstatus for gruppen. Litt uklart om 1) det er
   overhodet n�dvendig (0 moderatorer == ikke-moderert gruppe) 2) hvordan
   det skal implementeres, om overhodet (antageligvis en trait).

B�de VA og FA kan v�re medlemmer i den samme gruppen (vi burde dog legge inn
sperre for alle andre account_typer i API-et). Dog, det er kun FA som kan v�re
eiere og moderatorer av en VG. Igjen, dette sjekkes i API-et (siden db-skjema
ikke st�tter det).

Vi har allerede et opplegg for � uttrykke eierskap og moderatorstatus gjennom
rettighetsrammeverket til bofhd (``bofhd_auth.sql``). Vi kan endre eierskap og
moderasjonsstatus p� samme m�te som rettighetene tildeles i dag, si, ved UiO.

Gruppenavn i virthome m� ha en realm, p� samme m�te som VA sine navn -- alle
grupper kommer til � hete "<noe>@VH", der <noe> er opptil FA-en som lager
gruppen (s�fremt gruppenavnet ikke er tatt allerede).

Det skal til enhver tid v�re eksakt 1 eier av en VG. Eierskapet kan imidlertid
overdras til en annen bruker. Denne overdragelsen skjer gjennom et
bekreftelsessteg (f.eks. p� samme m�te som registrering av nye VA-er). Det er
kun n�v�rende eier som kan overdra eierskapet. Tilsvarende bekreftelse kreves
n�r eier eller moderator �nsker � melde en annen bruker som moderator.

Enhver bruker kan meldes inn i en gruppe (det kreves aktivt samtykke fra
brukeren, dog). Brukeren selv, gruppeeier og gruppemoderator kan melde en
bruker ut av gruppen. N�r brukeren meldes ut av gruppen av
gruppeeier/moderator, skjer dette i stillhet for brukeren. Fjerning av
medlemmer blir registrert i Cerebrum sitt change_log, s� vi har en oversikt
over hvilken konto meldte en gitt konto ut av en gruppe til enhver tid.

.. FIXME: Det er ogs� blitt foresl�tt at vi burde merke p� en eller annen m�te
   at gruppen har medlemmer fra usikre (VA) og tiltrodde kilder (FA), dog det 
   er kanskje mer et sp�rsm�l for presentasjonslaget.

Gruppemedlemskap uttrykkes gjennom ``group_member``, hvor det er helt
uproblematisk � blande sammen VA og FA innad samme gruppe.



Skjemautvidelsene
==================
Det er n�dvendig med et lite supplement til Cerebrum-skjema. Vi trenger en
unik identifikator for utest�ende change_log requests, og denne
identifikatoren b�r v�re passe stor/tilfeldig (mao ikke en entity_id eller
tstamp). Det er laget egen tabell, ``pending_change_log`` som knytter en slik
unik id mot ``change_log(change_id)``. Tabellen med alle skranker er i
``design/mod_virthome.sql``. Utover dette er det ingen skjemaendringer.

DB-modulene som vi trenger i VirtHome blir da:

  + ``mod_virthome.sql``
  + ``bofhd_auth.sql``
  + ``bofhd_tables.sql``
  + ``core_tables.sql``
  + ``mod_changelog.sql``
  + ``mod_entity_trait.sql``
  + ``mod_password_history.sql``



Bofhd-kommunikasjon
====================
I forhold til hvordan ting er blitt gjort tidligere, er det en rekke endringer
som m� introduseres i bofhd. 

Den overordnede oversikten er angitt i ``over-communication-sketch.dia``. 

Den spesifikk kommandosekvensen for de operasjonene som krever autorisasjon er
skissert i ``command-with-login.dia``. 


Innlogging
-----------
Bofhd er kodet slik at alle brukere m� autentisere seg f�r de kj�rer noen
kommandoer og privilegiene p� alle de p�f�lgende kommandoene sjekkes mot
sesjon-ID-en gitt ved innlogging. Denne tiln�rmingen er ikke s� gunstig for
VH: FA-er autentiserer seg mot Feide og VirtHome lagrer ikke deres passord
engang. Mao. tillittskjeden m� utvides og bofhd m� stole p� at
web-applikasjonen (web-frontend) har autentisert brukeren.

Imidlertid er problemet fortsatt der -- bofhd kan ikke bare kj�re vilk�rlige
kommandoer sendt av en eller annen FA/VA p� den andre enden av
oppkoblingen. Det foresl�s dermed � autentisere samt utf�re kommandoene p�
f�lgende m�te:

  #. VA-er logger seg inn direkte i VH sin bofhd. Her kreves det ingen
     spesialtilpasninger.

For FA-er, derimot, ser prosessen slik ut:

  #. Web-frontenden s�rger for � redirecte brukeren til rett
     autentiseringstjeneste (Moria? LDAP?) og f�r tilbake en bekreftelse p� at
     brukeren er autentisert [#auth1]_.
  #. Deretter logger web-frontenden seg mot bofhd som web-applikasjon. Det m�
     opprettes (p� forh�nd) egen bruker til web-applikasjonen med visse
     rettigheter i bofhd. Brukernavn/passord m� skrives (i klartekst) i en
     passende fil p� maskinen som kj�rer web-applikasjonen. Tilgangen til
     denne filen m� ikke gis til noen andre enn den brukeren som
     web-applikasjonen kj�rer som. Tanken med denne er � kreve at den som
     kobler seg mot bofhd kjenner til en eller annen hemmelig n�kkel, slik at
     ikke hvem som helst skal kunne logge seg inn mot bofhd, enda bofhd st�r
     p� et nett med begrenset tilgang (forh�pentligvis).
  #. Deretter gj�r web-frontend en "su <bruker>" kommando, for � registrere at
     alle de p�f�lgende kommandoene kj�res som "<bruker>". Mao, bofhd
     tilordner den eksisterende web-frontend sesjon til en annen bruker. Det er
     viktig � begrense mengden av brukere som f�r lov til � bytte eierskapet
     til sesjonen mot bofhd (i prinsippet er det kun web-applikasjonen som
     skal trenge det).
  #. Deretter kan kommandoene fra brukeren sendes via web-applikasjonen til
     bofhd (slik det er i dag med jbofh, cweb, osv.).

Siden kommunikasjonen mellom wep-applikasjonen foreg�r over HTTPS, er det
ingen mulighet for � avlytte sesjon-ID-en og misbruke den. Svakheten i denne
l�sningen er at web-applikasjonen m� ha tilgang til sitt eget
brukernavn/passord i klartekst. Blir web-applikasjonen eller web-tjeneren
kompromittert, vil angriperen kunne endre sesjonseierskap (og dermed
rettighetene knyttet til sesjonen) til hvilken som helst bruker i VirtHome.

For � oppsummere, dagens ordning med "innlogging f�r kommando" best�r, men i
en noe endret form.  

En annen viktig del av saken er at i VirtHome m� det finnes en rekke
kommandoer som ikke krever innlogging fra brukernes side (registrering av en
ny VA, det � bekrefte en foresp�rsel sendt per e-post). Per design er det slik
at hvem som helst skal kunne opprette en ny VA uten noe tidligere tilknytningn
til VirtHome. Dette betyr at web-applikasjonen m� kunne ikke bare gj�re "su
<bruker>" men ogs� videreformidle slike
kommandoer-fra-brukere-uten-autentisering. Naturligvis vil web-applikasjonen
fremdeles m�tte logge seg inn til bofhd og s� sende en "opprett en ny
VA"-kommando til bofhd (som seg selv, heller enn p� vegne av en annen bruker).

.. [#auth1] Akkurat hvordan dette gjennomf�res praktisk er ikke s� veldig
            interessant her. Vi bare antar at det finnes en tjeneste som
            web-applikasjonen kan bruke for � f� en bekreftelse p� at brukeren
            som logger seg inn er den vedkommende p�st�r � v�re.


Hendelsesforl�p
-----------------
La oss se p� hendelsesforl�p i f�lgende situasjoner knyttet til bofhd / dens
bruk. 

Innlogging av VA
~~~~~~~~~~~~~~~~~
  #. Brukeren velger den websiden der h*n kan logge seg inn som en VA.
  #. Brukeren blir presentert med en side der vedkommende fyller ut brukernavn
     og passord og sender disse til webappen.
  #. webapp logger seg inn i bofhd (``bofhd_login``) med det supplerte
     brukernavnet og passordet. 
  #. bofhd sjekker brukernavnet/passordet, og tilordner sesjonen til den
     aktuelle brukeren.

Fra det tidspunktet av er VA autentisert og kan utf�re kommandoer med dertil
passende rettigheter/tilganger.

Innlogging av en FA
~~~~~~~~~~~~~~~~~~~~~
  #. Brukeren velger den websiden der h*n kan logge seg inn som feide-bruker.
  #. Brukeren autentiserer seg mot feide
  #. webapp f�r en datablobb fra brukeren/feide
  #. webapp logger seg inn i bofhd med eget brukernavn/passord
  #. webapp kaller ``user_fedaccount_login`` med parametre fra blobben
     (brukernavn, e-post, personnavn. Vi krever minst disse 3)
  #. dersom det brukernavnet ikke finnes i virthome, opprettes det av bofhd.
  #. deretter tilordner bofhd sesjonen til den aktuelle brukeren (webapp
     eier ikke lenger sesjonen og alle kommandoer utf�res med privilegiene til
     brukeren).

Gruppeinvitasjon
~~~~~~~~~~~~~~~~~~
F�dererte brukere kan opprette grupper i virthome (f.eks. med det form�let �
styre tilgangen til blogg/wiki). En FA kan invitere i en gruppe som
vedkommende eier/modererer andre brukere. Siden de inviterte er ikke
n�dvendigvis registrert i virthome, baseres invitasjonsutsendelsen p�
e-postadresser.

Hendelsesforl�pet blir da:

   #. En FA logger seg inn (beskrevet tidligere)
   #. FA velger ut gruppen og e-postadressene som skal inviteres til den. 
   #. For hver e-postadresse lages det en invitasjon i bofhd (webapp kaller
      ``bofhd_group_invite``)
   #. For hver slik invitasjon, lages det en bofhd_request og webappen f�r
      tilbake et engangspassord (OTP)
   #. Webapp sender e-post med invitasjonen til den gitte e-postadressen der
      OTP er bakt inn.
   #. E-postmottageren f�lger linken med OTP bakt inn.

Deretter er det flere mulige scenarioer: den inviterte er en FA, er en VA som
alt finnes i virthome eller er en VA som ikke er registrert i
virthome. Hendelsesforl�pene blir da hhv:

  * For en FA:

     #. logge seg inn i virthome (slik beskrevet tidligere)
     #. ``user_confirm_request(OTP)`` som vil da melde FA-en (som eier
        bofhd-sesjonen) inn i den gruppen som er assosiert med OTP.

  * For en VA som finnes:

     #. logge seg inn i virthome (slik beskrevet tidligere)
     #. ``user_confirm_request(OTP)`` p� samme m�te som for FA.

  * For en VA som ikke finnes:

     #. webapp finner ut hvilken e-postadresse OTP ble sendt til
        (``request_parameters``)
     #. Brukeren f�r beskjed om � registrere seg, hvor vedkommende f�r fylle
        ut alle felt, bortsett fra e-post.
     #. Brukeren registrerer seg. P� dette tidspunkt er det ikke n�dvendig �
        bekrefte e-postadressen (vi vet jo hvilken e-postadresse en gitt
        invitasjon er blitt sendt til)
     #. webappen kaller ``user_confirm_request(OTP)`` p� samme m�te som for
        FA for � melde den nye VA inn i gruppen.

   Legg merke til at dette er den eneste m�ten som nye VA-er kan oppst� i
   VirtHome. Det skal ikke finnes en annen m�te � f� opprettet VA-er.

Passordgjenopprettelse
~~~~~~~~~~~~~~~~~~~~~~~
Naturlig nok m� vi ha et opplegg for passordgjenopprettelse. Ideen er at
VA-brukerne som glemmer innloggingspassordet i VH skal kunne f� et nytt
passord. Vi m� s�rge for at eksisterende brukere ikke kan bare bli DoS-et ut
av VH, og derfor foreg�r passordbytte f�rst etter at vi f�r bekreftet at en
gitt e-postadresse virkelig *�nsker* � f� passordet byttet. 

For ordens skyld, passordet blir gjenopprettet i den forstand at det gamle
passordet blir utlevert i klartekst; vi lager et nytt passord (n�r det blir
aktuelt) og setter det. Brukeren f�r s� et nytt passord og kan da bytte
det. Dersom vi lager tilstrekkelig kjipe automatiske passord, blir folk
tvunget til � bytte det autogenererte passordet med en gang selv :)

Da foreg�r situasjonen slik:

  #. Brukeren kommer til en webside der vedkommende fyller ut e-postadresse OG
     brukernavn og trykker p� "recover my password"
  #. webapp logger seg inn i bofhd (som seg selv) og kaller
     ``user_recover_password(email, uname)``
  #. bofhd lager en request, der email/uname noteres og returnerer OTP til
     webapp. 
  #. webapp sender en e-post til den aktuelle e-postadressen med en link
     tilbake med OTP.
  #. Brukeren trykker p� linken og kommer til en side der vedkommende fyller
     ut det nye passordet sitt.
  #. webapp logger seg inn som seg selv og kj�rer
     ``user_confirm_request(OTP, nytt passord)``. 
  #. bofhd sjekker og setter det nye passordet.


Kommandoer som krever bekreftelse
----------------------------------
En rekke kommandoer i VirtHome vil kreve et bekreftelsessteg, siden en
trykkfeil vil potensielt kunne �delegge for brukeren eller skape merarbeid for
oss. Dette gjelder endring av e-post for VA-er, gruppeinvitasjon, overdragelse
av eierskap til en gruppe, osv.

I utgangspunktet var planen � bruke traits til dette. Imidlertid kan det v�re
mye tilstandsinformasjon knyttet til en bekreftelse, og da er det enklere �
bruke ``change_log`` til form�let (traits har ikke en CLOB/BLOB knyttet til
seg som man kan stappe parametre i, change_log har det -- ``change_params``;
vi trenger nok � kunne lagre en del tilstandsinformasjon knyttet til en slik
bekreftelseshendelse).

S�, gitt en handling som krever en bekreftelse, der handlingen har en rekke
parametre P, vil f�lgende skje i dag:

  #. Man lager en unik request-id, som skal identifiseres handlingen
     entydig. Vi bruker UUID4, men hva som helst langt og tilfeldig
     duger. 
  #. Parametre P til handlingen samles i en dict
  #. Det lages en ny change_log event, som:

       * ... har ``change_params`` satt til ``pickle.dumps(P)`` (mao. den er satt
         til den picklede parameterdict-en (ja, det er brudd p� 1NF, og det er
         trist, men slik er det).
       * ... har ``subject_entity`` pekende p� den entiteten som bekreftelsen
         gjelder.
       * ... er forbundet med den unike request-id-en. 

     Den siste biten er n�dvendig for � kunne finne igjen en spesifikk
     change_log event senere.
  #. Den unike request-iden returneres tilbake til webapplikasjonen.

.. (FIXME: vi trenger en vurdering av sikkerhetssjefen p� akkurat dette).

Planen er da som f�lgende. En bruker utf�rer en handling i webapp-en som
krever bekreftelse. webapp-en kaller en kommando i bofhd som lager en slik
bekreftelse (i change_log) og returnerer request-id til webappen. webappen
sender en e-post til brukeren der det er bakt inn en URL tilbake til virthome
med request-id som en parameter. N�r brukeren f�r e-post og trykker p� linken
i e-posten, kaller webapp en kommando i bofhd med request-id-en (tatt fra
HTTP-parameteren/URL-en) som argument. bofhd da utf�rer den aktuelle
handlingen, og sletter change_log-eventen.

Det alene er ikke tilstrekkelig, siden vi m� rydde opp i events som ikke er
blitt bekreftet. ``reaper.py`` er ment til det form�let (siden alle
``change_log``-hendelser har et tidsstempel). Det er slik at vi etterstreber �
ikke endre tilstanden i VH f�r en hendelse er blitt bekreftet; f.eks. gitt en
foresp�rsel om � bytte e-post for en VA, eksisterer VA-en med den gamle
e-postadressen helt fram til bekreftelsesmeldingen mottas (e-postadressen
skiftes f�rst da).


Rettighetsforvaltning i bofhd
------------------------------
Per i dag er de aller fleste (alle?) kommandoer i bofhd implementert slik at
det sjekkes om brukeren som utf�rer kommandoen har rett til � utf�re
den. Denne ordningen kan gjerne best� i VirtHome-utgaven ogs�. Imidlertid er
det slik at noen av kommandoene skal kunne kj�res av VirtHome-brukere uten at
de skal trenge � logge seg inn. Alle kommandoene skal formidles via
web-applikasjonen uansett. Dette betyr at for en rekke kommandoer (slik som
opprettelse av nye VA-er), er det web-applikasjonen selv som vil utf�re dem
(heller en eller annen spesifikk VA/FA). Rettighetene kan s�ledes hektes p�
systemkontoen tildelt web-applikasjonen. Eksempelvis vil ikke noen andre
trenge � ha tilgang til opprettelse av virtaccount enn nettopp
web-applikasjonen i VirtHome-bofhd.

N� er det slik at bofhd er bygget rundt ideen om at enhver kommando (selv en
uten restriksjoner) ikke kan kj�res uten at brukeren er loggen inn. For
virthome passer dette en smule d�rlig. Det finnes dog en l�sning: kommandoer
som ikke krever innlogging (f.eks. det � lage en ny bruker eller � utf�re en
bekreftelse) utf�res av web-applikasjonen (som da alltid logger seg in);
kommandoer som utf�res av en VA kan utf�res etter at vedkommende logget seg
inn (vi har de krypterte passordene i Cerebrum, og autentisering er triviell);
kommandoer som utf�res av en FA kan utf�res etter at webapp gir beskjed til
bofhd om at brukeren er autentisert. Det siste krever naturligvis at bofhd
stoler p� at webapp har rett n�r den sier at dens sesjon skal byttes til en
annen bruker.
