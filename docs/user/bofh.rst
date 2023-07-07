====================================
Brukeradministrasjon med bofh
====================================

Innledning
================

Dette kapittelet tar for seg virkem�ten til programmet bofh/jbofh.
Det tar ikke for seg de enkelte kommandoer, utover noen enkle
eksempler.  Dokumentasjon av de enkelte kommandoer finnes her: TODO.


Hva er bofh?
=============

Bofh er en enkel kommandolinjebasert klient som prater med en bofhd
server.  Brukeren oppgir kommandoer som sendes til en server.  Serveren
tolker kommandoen, og sender et svar tilbake.  Klienten formaterer
dette svaret, og viser det p� skjermen.

Bruk av bofh
==============


Oppstart og innlogging
----------------------
bofh distribueres som en jar fil.  De fleste steder har
systemadministratoren installert et wrapper-script slik at man kan
starte bofh ved � skrive ``bofh``::

  ~@maskinami> bofh
  Bofhd server is at https://cerebrum.uio.no:8000
  Password for mittbrukernavn:

bofh starter da med � fortelle hvilken bofh server den prater med, og
sp�r etter passord.  Det kommer ingen ting p� skjermen n�r man skriver
inn passord.  Etter innlogging, f�r man opp en velkomstmelding, og blir
m�tt av bofh promptet (normalt ``jbofh>``).  Noen ganger vil man f� en
melding, en s�kalt motd, f�r velkomstmeldingen. ::

  ~@maskinami> bofh
  Bofhd server is at https://cerebrum.uio.no:8000
  Password for mittbrukernavn:
  motd: I dag er det gratis winerbr�d i kantina
  Welcome to jbofh, v 0.9.3, type "help" for help
  jbofh> 

Bruk av kommandoer
------------------

Kommandoer oppgis ved � skrive inn en kommando, fulgt av enter tasten.
Kommandoene er normalt bygget opp som::

  <hovedkommando> <underkommando> <argumenter>

For alle kommandoer som omhandler grupper, kan f.eks hovedkommandoen
v�re ``group``, mens underkommandoene kan v�re ``add``, ``info`` osv.

De forskjellige kommandoene tar et varierende antall argumenter.
Hvilke argumenter en kommando bruker, kan man finne ved � bruke
``help``.  Dersom man ikke har oppgitt nok argumenter til en kommando,
vil bofh sp�rre etter det manglende argumentet f�r kommandoen utf�res::

  jbofh> pquota status 
  Enter person id >

Dersom man ikke forst�r hva man skal oppgi som argument, kan man taste
? fulgt av enter::

  jbofh> pquota status 
  Enter person id >?
  Enter person id as idtype:id.
  If idtype=fnr, the idtype does not have to be specified.
  The currently defined id-types are:
    - fnr : norwegian f?dselsnummer.

Dette eksempelet illustrerer for�vrig en vanlig utvidelse: et argument
kan angis p� mer enn en m�te.  Eksempelvis skj�nner systemet at
argumentet er et f�dselsnummer dersom det best�r av 11 tall.  Det kan
ogs� forst� at hvis man har angitt et brukernavn, s� mener man
personen som eier denne brukeren.  Mange kommandoer lar en ogs� angi
den interne id'en til et attributt som entity_id:tall.  Dette anbefales
kun for viderekommende.


Universelle kommandoer
----------------------

* help

  Gir hjelp for systemet.  Uten argumenter, vises litt generell hjelp,
  samt de forskjellige hovedkommandoene.  Oppgis hovedkommando som
  argument, f�r man vist de ulike underkommandoene, mens hvis begge
  disse angis som argument, f�r man hjelp for en enkelt kommando.

  I hjelpen til en enkelt kommando er noen argumenter angitt i
  klammeparenteser.  Dette betyr at argumentet kan utelates.

* source

  Leser kommandoer fra fil.  Fungerer akkurat som om man hadde tastet de
  samme kommandoene p� kommandolinjen.

* quit

  Avslutter programmet.

* commands

  For internt bruk.  Viser definisjonen av de kommandoer brukeren har
  lov til � utf�re.


Dynamisk tildeling av kommandoer
--------------------------------

Hvilke kommandoer som er tilgjengelige for den enkelte bruker vil
variere b�de utifra hvilken bofh server man er tilkoblet, samt til
hvilke rettigheter man har.  Dersom bofh serveren er startet med en
tom konfigurasjons-fil, vil man kun ha tilgang til de universelle
kommandoene angitt ovenfor.  Bofh serveren forteller klienten hvilke
kommandoer som er tilgjengelige n�r brukeren logger inn.  Dersom
serveren re-startes, vil klienten automatisk oppdatere listen over
tilgjengelige kommandoer.


Kj�ring av flere like kommandoer i en operasjon
------------------------------------------------

Dersom et eller flere av argumentene til en kommando er skrevet i
parentes, vil kommandoen bli utf�rt enkeltvis p� hvert av argumentene
inne i parentesen.  Dersom kommandoen medf�rer en endring i databasen,
skjer endringen kun dersom alle endringene lykkes.  Skal man f.eks
melde brukerene ola og kari inn i gruppene gruppe1 og gruppe2, kan det
gj�res slik::

  jbofh> group remove (ola kari) (gruppe1 gruppe2)
  OK, ola added to gruppe1
  OK, ola added to gruppe2
  OK, kari added to gruppe1
  OK, kari added to gruppe2


Blanke tegn o.l.
-----------------

Dersom man trenger � oppgi et blankt tegn, kan man enten taste enter
f�r argumentet, slik at man blir spurt etter det, eller man kan
omslutte mellomrommet med " eller ', f.eks slik::
  
  jbofh> person set_name ola "That's ok"

Backslash (\\) behandles som et helt vanlig tegn.


Navigering p� kommandolinjen
-----------------------------

Dersom bofh sp�r om noe man ikke vil svare p�, kan man avbryte ved �
taste EOF-tasten.  P� unix er dette Ctrl-d.

Normalt er bofh kompilert med gnu-readline st�tte.  Det betyr at man
kan navigere frem og tilbake p� kommandolinjen med piltastene.  Pil
opp/ned blar tilbake/frem i kommandoer man har utf�rt tidligere.

For hoved og underkommando kan man benytte TAB-tasten for � automatisk
fylle ut resten av kommandoen dersom den er unik.  Man kan ogs� utelate
resten av tegnene s�fremt man har oppgitt nok tegn til at kommandoen er
unik.  F.eks kan man fritt velge om man vil skrive ``user info`` eller
``u i``.


Bruk p� windows maskiner
-------------------------

Dersom man starter bofh p� en windows maskin, evt. oppgir parameteren
``--gui`` p� kommandolinjen, �pnes bofh som et eget vindu der man
taster inn kommandoer nederst, og f�r tilbakemeldinger fra serveren p�
linjen over.  Denne klienten oppf�rer seg likt den vanlige klienten
med noen f� unntak:

* Man m� bruke ESC-tasten istedenfor Ctrl-d for � avbryte en kommando
  man er i ferd med � oppgi parametere til.  Dersom man st�r p�
  ``jbofh>`` promptet, vil ESC-tasten sp�rre om man skal avbryte
  programmet.

* Man f�r en scrollbar i feltet der tilbakemeldinger fra serveren
  vises.  H�yreklikk i dette feltet bringer frem en meny der man kan
  t�mme skjermen.

Opsjoner til bofh
-------------------
* ``--url url`` : angi en alternativ bofh server
* ``-u brukernavn`` : angi et annen brukernavn
* ``--gui`` : start med gui
* ``--nogui`` : start uten gui
* ``-d`` : sl� p� debug-informasjon (skrives i jbofh_debug.log)


Mer informasjon
=================

* `Protokollen som bofh benytter
  <../devel/bofh.html#communicating-with-bofhd>`_

  Nyttig lesing dersom man �nsker � skrive script som prater med bofh

* `Administrasjon av bofh serveren <../admin/bofh.html>`_


