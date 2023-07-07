====================================================
Spesifikasjoner for brukergrensesnittet til virthome
====================================================

.. admonition:: Needs review

   This is an old document, some of the instructions may be out of date.

.. contents:: Innholdsfortegnelse

Innledning
==========
Dette er en kravspesifikasjon for hvordan brukergrensesnittet for virthome skal
se ut og oppføre seg.

Virthome skal være et komplett system for å la brukere som er eksterne og som
det ikke er aktuelt å gi en gjestekonto eller lignende få tilgang til
tjenester ved UiO.

Backenden skal være cerebrum, og detaljer for den løsningen finnes i et annet
dokument. Da vi allerede har et webgrensesnitt til cerebrum som heter
brukerinfo kan virthome ta det som et utgangspunkt.

Målet er å gjenbruke så mye av brukerinfo-kodebasen som mulig, og kun legge
til funksjonalitet som ikke nå ligger i brukerinfo. Brukerinfo takler allerede
kommunikasjon med en cerebrum-base via en bofhd.

Funksjonalitet
==================
Brukergrensesnittet skal brukes av to forskjellige typer brukere som skal bli
presentert med forskjellige valg. Den ene gruppen er brukere uten føderert
tilknytning og den andre er for de som har en føderert tilknytning.

Fødererte brukere skal kunne:

  * Logge inn via FEIDE
  * Opprette grupper
  * Slette grupper de er eier for
  * Invitere en annen føderert bruker til å bli eier av en gruppe de eier ved bruk av e-postadresse
  * Invitere ufødererte og fødererte brukere inn i grupper ved hjelp av en e-postadresse
  * Fjerne brukere fra grupper
  * Legge til fødererte moderatorer til grupper de er eier av
  * Fjerne moderatorer fra grupper de er eier av
  * Bli med i grupper etter invitasjon

Ufødererte brukere skal kunne:

  * Registrere ny bruker kun etter invitasjon
  * Endre passord
  * Vise reglement
  * Vise oversikt over gruppemedlemskap
  * Godta å bli medlem av ny gruppe
  * Endre e-postadresse
  * Endre navnet sitt
  * Avvikle bruker

Implementasjon
================

Sider
=======
Følgende websider skal kunne vises

Felles
-------

Forside
""""""""
Her skal det være info om tjenesten og info som gjør at man kan forstå
de to valgene man får om å logge seg inn som enten føderert bruker eller
uføderert bruker. 

Invitasjon
"""""""""""
Når man blir invitert til en gruppe får man en e-post med en link som
inneholder en nøkkel som gir tilgang til gruppen. Følger man den linken
kommer man til en side som ligner på forsiden, med valg om man er føderert
eller ekstern bruker samt et ekstra valg for å registrere seg selv.

Er man eksisterende bruker og følger en av de to linkene vil man komme til
innloggingssiden for den typen brukere og vil etter innlogging
bli meldt inn i gruppen.

Velger man å registrere seg vil man bli sendt til en egen registreringsside.

Fødererte brukere
--------------------

Feide-innlogging
"""""""""""""""""""
Trykker brukeren på feide-innloggingslinken som er på forsiden vil brukeren
bli sendt rett til feide sin side. Etter vellykket pålogging vil brukeren bli
videresendt til denne siden, som vil lagre info om brukeren som vi får fra feide og opprette en session
mot bofhd. Hvis brukeren ikke finnes i brukerdatabasen vil den automatisk bli
opprettet. Brukeren blir så automatisk bli videresendt til hovedsiden for
fødererte brukere.

Hovedside (fødererte brukere)
""""""""""""""""""""""""""""""
Oversiktsside med info om hvilke data vi har lagret om brukeren, samt en link
til gruppesiden.

Grupper
""""""""""""
Vise liste over alle grupper brukeren er eier av, er moderator av eller er
medlem av. Det skal være en link på hver gruppe til en side med mer info om
gruppen for de gruppene brukeren enten er eier eller moderator av.

Gruppeside
"""""""""""""""
En side per gruppe, som er linket opp fra "Your groups". Den skal inneholde
info om hvem som er medlem i gruppen og mulighet for å melde dem ut.
Det skal være mulig å legge til brukere som medlemmer av gruppen, og det gjøres
kun ved hjelp av e-postadresser.

Det skal også være et valg for å legge ned gruppen. Da vil alle brukerene bli meldt
av gruppen og gruppen vil bli satt inaktiv.

Ufødererte brukere
---------------------

Innlogging
"""""""""""
Innloggingssiden for ufødererte brukere kan se identisk ut som dagens
brukerinfo-innlogging, og bruke de samme mekanismene.

Hovedside (ufødererte brukere)
"""""""""""""""""""""""""""""""
Oversiktsside med linker til account og groups-siden.

Account
"""""""""""""""
Skal vise informasjon som er registrert om brukeren:

* e-postadresse
* Navn

Siden skal også gi brukeren mulighet til å endre e-postadressen, navnet
og passordet i tillegg gi muligheten for å slette kontoen. (I praksis
sette den innaktiv)

Når brukeren skal foreta et passordbytte må brukeren oppgi nåværende
passord, samt nytt passord to ganger. Dette er for å hindre at det nye
passordet blir feilstavet.

Groups
""""""""""""
Vise liste over alle grupper brukeren er medlem av med en beskrivelse av
gruppene. Det skal være mulig for brukeren å melde seg ut av enkeltgrupper.


Registreringsside
""""""""""""""""""
Her kommer man etter å ha blitt invitert til en gruppe og man ikke har
en konto enda.
Her må man oppgi ønsket brukernavn og passord, samt godta reglementet.

Glemt passord
""""""""""""""
På denne siden kan en bruker som har glemt passordet sitt skrive inn
brukernavnet sitt. Vi vil da sende ut en e-post til den registrerte
e-postadressen for den kontoen med en link til en side hvor brukeren kan
sette et nytt passord.

Registrering
""""""""""""""
Her vil brukeren trenge å fylle ut navn, ønsket brukernavn og ønsket passord.
Siden vi alt har en verifisert e-postadresse trenger vi ikke spørre om det.
Hvis brukeren heller vil ha en annen e-postadresse assosiert med kontoen
kan den enkelt byttes senere.

Etter oppretting
""""""""""""""""
Infoside som sier at kontoen er opprettet og at det skal fungere
å logge inn på tjenesten de har blitt invitert til innen få minutter.
Det skal også være en link til tjenesten og en link til innloggingssiden
til virthome.

Token-verifisering
""""""""""""""""""
Her blir den oppgitte tokenen verifisert mot det vi har lagret og hvis den
stemmer blir e-postadressen verifisert.
