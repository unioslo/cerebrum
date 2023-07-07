=========================================================
Spesifikasjoner for kommandosettet til BOHFD til virthome
=========================================================

.. contents:: Innholdsfortegnelse


Forkortelser
=============
  * OTP - One-Time password. Dette er en tilfeldig nøkkel som brukes for å
    kjennetegne handlinger som krever en bekreftelse. Denne nøkkelen skal være
    et tilfeldig passord som er ment til å brukes kun én gang for å utføre en
    spesifikk tilstandsendring (f.eks. skifte e-postadresse fra A til B).
  * FA - Federated Account, altså, en bruker med føderert tilknytning.
  * VA - VirtAccount, altså, en bruker uten føderert tilknytning.


BOFHD kommandoer
==================

user_confirm_request(OTP)
-----------------------------
Utfør en bekreftelse av en handling. Det er slik at visse kommandoer
resulterer i at en forespørsel om bekreftelse blir utsendt. Denne kommandoen
brukes (kun av webapp) til å be bofhd om å faktisk utføre handlingen som er
blitt bedt bekreftet. OTP i seg selv er tilstrekkelig for å finne ut hva slags
forespørsel dette gjelder og hvilke entiteter omfattes av den.


user_virtaccount_join_group(OTP, brukernavn, e-postadresse, passord, expire-date, navn)
-----------------------------------------------------------------------------------------
Oppretter en ny VA. Den nye brukeren vil havne i korrekt gruppe automatisk
(OTP-en brukes for å finne hvilken gruppe en nyopprettet VA skal havne i).


user_fedaccount_nuke(brukernavn)
--------------------------------
Sletter en spesifikk FA fra VirtHome.


user_fedaccount_login(brukernavn, e-postadresse, expire-date, navn)
------------------------------------------------------------------------
Logger inn en føderert bruker. Dersom ingen data om FA finnes i virthome,
opprettes det automatisk en passende FA.


user_su(brukernavn)
--------------------
Bytte nåværende sesjonen til en annen bruker. Denne kommandoen er tilgjengelig
kun for den brukeren som er spesiallaget til webapplikasjonen.


user_request_info(OTP)
-----------------------------
Returnerer info om requesten som er forbundet med OTP. Denne brukes der webapp
trenger å finne ut hvilken tilstandsendring en gitt OTP tilsvarer (f.eks. når
nye brukere skal opprettes og bli med i en gruppe, brukes denne metoden for å
finne ut hvilken gruppe og e-postadresse invitasjonen som tilsvarer OTP
gjelder)


user_info(brukernavn)
----------------------
Returnerer info om den gitte brukeren. Superbrukere og sudoers har lov til å se
informasjon om andre. Det listes opp e-postadresse, navn på eieren, spreads,
karantener, expire-dato, og gruppene vedkommende eier og modererer.


user_accept_eula(eula-type)
----------------------------
Godkjenn reglementet for operatoren. <eula-type> spesifiserer hvilket
reglement brukeren har godkjent.


user_change_password(gammelt_passord, nytt_passord)
---------------------------------------------------
Bytter ut det gamle passordet med det nye så lenge det gamle passordet stemmer,
og det nye passordet følger passordreglene. Denne operasjonen endrer også
expire-dato til å være 1 år i framtiden.


user_change_email(ny_e-postadresse)
-------------------------------------
Oppretter en forespørsel om å bytte e-postadressen til brukeren som er logget
inn. Forespørselen må bekreftes eksplisitt (jfr. user_confirm_request) og det
er først da at e-postadressen blir faktisk endret. Kommandoen returnerer en
OTP, som er ment til å brukes senere i user_confirm_request.


user_change_human_name(nytt_navn)
----------------------------------
Bytter eiernavnet registrert på brukeren til det som er oppgitt.


group_create(gruppenavn, beskrivelse, eier, URL)
-----------------------------------------------------
Oppretter en ny gruppe med infoen som er gitt.


group_disable(gruppenavn)
-----------------------------
Melder alle medlemmene av gruppen og setter den inaktiv. Dette er essensielt
"sletting", bortsett fra at gruppeentiteten blir liggende igjen for å ta vare
på gruppenavnet. Bare superbruker og eier kan gjøre dette.


group_remove_members(brukernavn, gruppenavn)
--------------------------------------------
Melder av brukeren av gruppen. Eiere/moderatorer kan melde hvem som helst ut
av sine grupper. En vilkårlig bruker kan melde seg selv ut av en gruppe der
vedkommende er medlem.


group_list(gruppenavn)
-----------------------------
Lister medlemmer til gruppen.


user_list_memberships
----------------------
Lister alle gruppemedlemsskapene til brukeren som kaller funksjonen.


group_change_owner(e-postadresse, gruppenavn)
-------------------------------------------------
Lager en forespørsel for at e-postadressen skal erstatte gruppens
eier. Returnerer en nøkkel som må bekreftest med user_confirm_request.


group_invite_moderator(e-postadresse, gruppenavn)
---------------------------------------------------
Lager en request for at e-postadressen skal bli med i gruppen
som moderator. Returnerer en nøkkel som må bekreftes med
user_confirm_request.


group_remove_moderator(brukernavn, gruppenavn)
-------------------------------------------------
Fjerner brukeren fra gruppen som moderator.


group_invite_user(e-postadresse, gruppenavn)
---------------------------------------------
Kjøres når en eier/moderator vil invitere en bruker til sin gruppe.
Funksjonen returnerer en key som senere må bli brukt av brukeren med et kall
på user_confirm_request.

Dette er i praksis den eneste måten hvordan nye VA-er kan oppstå i Cerebrum.


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



