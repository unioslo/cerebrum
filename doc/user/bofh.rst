====================================
Brukeradministrasjon med bofh
====================================

Innledning
================

Dette kapittelet tar for seg virkemåten til programmet bofh/jbofh.
Det tar ikke for seg de enkelte kommandoer, utover noen enkle
eksempler.  Dokumentasjon av de enkelte kommandoer finnes her: TODO.


Hva er bofh?
=============

Bofh er en enkel kommandolinjebasert klient som prater med en bofhd
server.  Brukeren oppgir kommandoer som sendes til en server.  Serveren
tolker kommandoen, og sender et svar tilbake.  Klienten formaterer
dette svaret, og viser det på skjermen.

Bruk av bofh
==============


Oppstart og innlogging
----------------------
bofh distribueres som en jar fil.  De fleste steder har
systemadministratoren installert et wrapper-script slik at man kan
starte bofh ved å skrive ``bofh``::

  ~@maskinami> bofh
  Bofhd server is at https://cerebrum.uio.no:8000
  Password for mittbrukernavn:

bofh starter da med å fortelle hvilken bofh server den prater med, og
spør etter passord.  Det kommer ingen ting på skjermen når man skriver
inn passord.  Etter innlogging, får man opp en velkomstmelding, og blir
møtt av bofh promptet (normalt ``jbofh>``).  Noen ganger vil man få en
melding, en såkalt motd, før velkomstmeldingen. ::

  ~@maskinami> bofh
  Bofhd server is at https://cerebrum.uio.no:8000
  Password for mittbrukernavn:
  motd: I dag er det gratis winerbrød i kantina
  Welcome to jbofh, v 0.9.3, type "help" for help
  jbofh> 

Bruk av kommandoer
------------------

Kommandoer oppgis ved å skrive inn en kommando, fulgt av enter tasten.
Kommandoene er normalt bygget opp som::

  <hovedkommando> <underkommando> <argumenter>

For alle kommandoer som omhandler grupper, kan f.eks hovedkommandoen
være ``group``, mens underkommandoene kan være ``add``, ``info`` osv.

De forskjellige kommandoene tar et varierende antall argumenter.
Hvilke argumenter en kommando bruker, kan man finne ved å bruke
``help``.  Dersom man ikke har oppgitt nok argumenter til en kommando,
vil bofh spørre etter det manglende argumentet før kommandoen utføres::

  jbofh> pquota status 
  Enter person id >

Dersom man ikke forstår hva man skal oppgi som argument, kan man taste
? fulgt av enter::

  jbofh> pquota status 
  Enter person id >?
  Enter person id as idtype:id.
  If idtype=fnr, the idtype does not have to be specified.
  The currently defined id-types are:
    - fnr : norwegian f?dselsnummer.

Dette eksempelet illustrerer forøvrig en vanlig utvidelse: et argument
kan angis på mer enn en måte.  Eksempelvis skjønner systemet at
argumentet er et fødselsnummer dersom det består av 11 tall.  Det kan
også forstå at hvis man har angitt et brukernavn, så mener man
personen som eier denne brukeren.  Mange kommandoer lar en også angi
den interne id'en til et attributt som entity_id:tall.  Dette anbefales
kun for viderekommende.


Universelle kommandoer
----------------------

* help

  Gir hjelp for systemet.  Uten argumenter, vises litt generell hjelp,
  samt de forskjellige hovedkommandoene.  Oppgis hovedkommando som
  argument, får man vist de ulike underkommandoene, mens hvis begge
  disse angis som argument, får man hjelp for en enkelt kommando.

  I hjelpen til en enkelt kommando er noen argumenter angitt i
  klammeparenteser.  Dette betyr at argumentet kan utelates.

* source

  Leser kommandoer fra fil.  Fungerer akkurat som om man hadde tastet de
  samme kommandoene på kommandolinjen.

* quit

  Avslutter programmet.

* commands

  For internt bruk.  Viser definisjonen av de kommandoer brukeren har
  lov til å utføre.


Dynamisk tildeling av kommandoer
--------------------------------

Hvilke kommandoer som er tilgjengelige for den enkelte bruker vil
variere både utifra hvilken bofh server man er tilkoblet, samt til
hvilke rettigheter man har.  Dersom bofh serveren er startet med en
tom konfigurasjons-fil, vil man kun ha tilgang til de universelle
kommandoene angitt ovenfor.  Bofh serveren forteller klienten hvilke
kommandoer som er tilgjengelige når brukeren logger inn.  Dersom
serveren re-startes, vil klienten automatisk oppdatere listen over
tilgjengelige kommandoer.


Kjøring av flere like kommandoer i en operasjon
------------------------------------------------

Dersom et eller flere av argumentene til en kommando er skrevet i
parentes, vil kommandoen bli utført enkeltvis på hvert av argumentene
inne i parentesen.  Dersom kommandoen medfører en endring i databasen,
skjer endringen kun dersom alle endringene lykkes.  Skal man f.eks
melde brukerene ola og kari inn i gruppene gruppe1 og gruppe2, kan det
gjøres slik::

  jbofh> group remove (ola kari) (gruppe1 gruppe2)
  OK, ola added to gruppe1
  OK, ola added to gruppe2
  OK, kari added to gruppe1
  OK, kari added to gruppe2


Blanke tegn o.l.
-----------------

Dersom man trenger å oppgi et blankt tegn, kan man enten taste enter
før argumentet, slik at man blir spurt etter det, eller man kan
omslutte mellomrommet med " eller ', f.eks slik::
  
  jbofh> person set_name ola "That's ok"

Backslash (\\) behandles som et helt vanlig tegn.


Navigering på kommandolinjen
-----------------------------

Dersom bofh spør om noe man ikke vil svare på, kan man avbryte ved å
taste EOF-tasten.  På unix er dette Ctrl-d.

Normalt er bofh kompilert med gnu-readline støtte.  Det betyr at man
kan navigere frem og tilbake på kommandolinjen med piltastene.  Pil
opp/ned blar tilbake/frem i kommandoer man har utført tidligere.

For hoved og underkommando kan man benytte TAB-tasten for å automatisk
fylle ut resten av kommandoen dersom den er unik.  Man kan også utelate
resten av tegnene såfremt man har oppgitt nok tegn til at kommandoen er
unik.  F.eks kan man fritt velge om man vil skrive ``user info`` eller
``u i``.


Bruk på windows maskiner
-------------------------

Dersom man starter bofh på en windows maskin, evt. oppgir parameteren
``--gui`` på kommandolinjen, åpnes bofh som et eget vindu der man
taster inn kommandoer nederst, og får tilbakemeldinger fra serveren på
linjen over.  Denne klienten oppfører seg likt den vanlige klienten
med noen få unntak:

* Man må bruke ESC-tasten istedenfor Ctrl-d for å avbryte en kommando
  man er i ferd med å oppgi parametere til.  Dersom man står på
  ``jbofh>`` promptet, vil ESC-tasten spørre om man skal avbryte
  programmet.

* Man får en scrollbar i feltet der tilbakemeldinger fra serveren
  vises.  Høyreklikk i dette feltet bringer frem en meny der man kan
  tømme skjermen.

Opsjoner til bofh
-------------------
* ``--url url`` : angi en alternativ bofh server
* ``-u brukernavn`` : angi et annen brukernavn
* ``--gui`` : start med gui
* ``--nogui`` : start uten gui
* ``-d`` : slå på debug-informasjon (skrives i jbofh_debug.log)


Mer informasjon
=================

* `Protokollen som bofh benytter
  <../devel/bofh.html#communicating-with-bofhd>`_

  Nyttig lesing dersom man ønsker å skrive script som prater med bofh

* `Administrasjon av bofh serveren <../admin/bofh.html>`_


