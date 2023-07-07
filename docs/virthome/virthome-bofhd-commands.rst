=========================================================
Spesifikasjoner for kommandosettet til BOHFD til virthome
=========================================================

.. contents:: Innholdsfortegnelse


Forkortelser
=============
  * OTP - One-Time password. Dette er en tilfeldig n�kkel som brukes for �
    kjennetegne handlinger som krever en bekreftelse. Denne n�kkelen skal v�re
    et tilfeldig passord som er ment til � brukes kun �n gang for � utf�re en
    spesifikk tilstandsendring (f.eks. skifte e-postadresse fra A til B).
  * FA - Federated Account, alts�, en bruker med f�derert tilknytning.
  * VA - VirtAccount, alts�, en bruker uten f�derert tilknytning.


BOFHD kommandoer
==================

user_confirm_request(OTP)
-----------------------------
Utf�r en bekreftelse av en handling. Det er slik at visse kommandoer
resulterer i at en foresp�rsel om bekreftelse blir utsendt. Denne kommandoen
brukes (kun av webapp) til � be bofhd om � faktisk utf�re handlingen som er
blitt bedt bekreftet. OTP i seg selv er tilstrekkelig for � finne ut hva slags
foresp�rsel dette gjelder og hvilke entiteter omfattes av den.


user_virtaccount_join_group(OTP, brukernavn, e-postadresse, passord, expire-date, navn)
-----------------------------------------------------------------------------------------
Oppretter en ny VA. Den nye brukeren vil havne i korrekt gruppe automatisk
(OTP-en brukes for � finne hvilken gruppe en nyopprettet VA skal havne i).


user_fedaccount_nuke(brukernavn)
--------------------------------
Sletter en spesifikk FA fra VirtHome.


user_fedaccount_login(brukernavn, e-postadresse, expire-date, navn)
------------------------------------------------------------------------
Logger inn en f�derert bruker. Dersom ingen data om FA finnes i virthome,
opprettes det automatisk en passende FA.


user_su(brukernavn)
--------------------
Bytte n�v�rende sesjonen til en annen bruker. Denne kommandoen er tilgjengelig
kun for den brukeren som er spesiallaget til webapplikasjonen.


user_request_info(OTP)
-----------------------------
Returnerer info om requesten som er forbundet med OTP. Denne brukes der webapp
trenger � finne ut hvilken tilstandsendring en gitt OTP tilsvarer (f.eks. n�r
nye brukere skal opprettes og bli med i en gruppe, brukes denne metoden for �
finne ut hvilken gruppe og e-postadresse invitasjonen som tilsvarer OTP
gjelder)


user_info(brukernavn)
----------------------
Returnerer info om den gitte brukeren. Superbrukere og sudoers har lov til � se
informasjon om andre. Det listes opp e-postadresse, navn p� eieren, spreads,
karantener, expire-dato, og gruppene vedkommende eier og modererer.


user_accept_eula(eula-type)
----------------------------
Godkjenn reglementet for operatoren. <eula-type> spesifiserer hvilket
reglement brukeren har godkjent.


user_change_password(gammelt_passord, nytt_passord)
---------------------------------------------------
Bytter ut det gamle passordet med det nye s� lenge det gamle passordet stemmer,
og det nye passordet f�lger passordreglene. Denne operasjonen endrer ogs�
expire-dato til � v�re 1 �r i framtiden.


user_change_email(ny_e-postadresse)
-------------------------------------
Oppretter en foresp�rsel om � bytte e-postadressen til brukeren som er logget
inn. Foresp�rselen m� bekreftes eksplisitt (jfr. user_confirm_request) og det
er f�rst da at e-postadressen blir faktisk endret. Kommandoen returnerer en
OTP, som er ment til � brukes senere i user_confirm_request.


user_change_human_name(nytt_navn)
----------------------------------
Bytter eiernavnet registrert p� brukeren til det som er oppgitt.


group_create(gruppenavn, beskrivelse, eier, URL)
-----------------------------------------------------
Oppretter en ny gruppe med infoen som er gitt.


group_disable(gruppenavn)
-----------------------------
Melder alle medlemmene av gruppen og setter den inaktiv. Dette er essensielt
"sletting", bortsett fra at gruppeentiteten blir liggende igjen for � ta vare
p� gruppenavnet. Bare superbruker og eier kan gj�re dette.


group_remove_members(brukernavn, gruppenavn)
--------------------------------------------
Melder av brukeren av gruppen. Eiere/moderatorer kan melde hvem som helst ut
av sine grupper. En vilk�rlig bruker kan melde seg selv ut av en gruppe der
vedkommende er medlem.


group_list(gruppenavn)
-----------------------------
Lister medlemmer til gruppen.


user_list_memberships
----------------------
Lister alle gruppemedlemsskapene til brukeren som kaller funksjonen.


group_change_owner(e-postadresse, gruppenavn)
-------------------------------------------------
Lager en foresp�rsel for at e-postadressen skal erstatte gruppens
eier. Returnerer en n�kkel som m� bekreftest med user_confirm_request.


group_invite_moderator(e-postadresse, gruppenavn)
---------------------------------------------------
Lager en request for at e-postadressen skal bli med i gruppen
som moderator. Returnerer en n�kkel som m� bekreftes med
user_confirm_request.


group_remove_moderator(brukernavn, gruppenavn)
-------------------------------------------------
Fjerner brukeren fra gruppen som moderator.


group_invite_user(e-postadresse, gruppenavn)
---------------------------------------------
Kj�res n�r en eier/moderator vil invitere en bruker til sin gruppe.
Funksjonen returnerer en key som senere m� bli brukt av brukeren med et kall
p� user_confirm_request.

Dette er i praksis den eneste m�ten hvordan nye VA-er kan oppst� i Cerebrum.


group_info(gruppenavn)
-----------------------------
Returnerer info om gruppen, eier, moderatorer og
medlemmer.


spread_add(type, entitet, spread)
----------------------------------
Gi en gitt spread til en gitt entitet. Kommandoen er forbeholdt superbrukere. 


spread_remove(type, entitet, spread)
-------------------------------------
Det omvendte av spread_add(). 


spread_list()
--------------
Liste alle spreads som finnes i VH.


spread_entity_list(type, entitet)
----------------------------------
Liste alle spreads for en gitt entitet. Kommandoen er forbeholdt superbrukeren
og entiteten selv (man kan selv se egne spreads).


quarantine_add(entity_type, ident, karantenetype, grunn, sluttdato)
--------------------------------------------------------------------
Sette en gitt entitet i en gitt karantene. Forbeholdt superbrukeren.


quarantine_remove(entity_type, entity_ident, karantenetype)
------------------------------------------------------------
Det omvendte av quarantine_add().


quarantine_list()
-----------------
Lister opp alle karantener.


quarantine_show(entity_type, entity_id)
---------------------------------------
Viser alle karantener til en gitt entitet.



