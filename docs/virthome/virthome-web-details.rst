====================================================
Spesifikasjoner for brukergrensesnittet til virthome
====================================================

.. contents:: Innholdsfortegnelse

Innledning
==========
Dette er en kravspesifikasjon for hvordan brukergrensesnittet for virthome skal
se ut og oppf�re seg.

Virthome skal v�re et komplett system for � la brukere som er eksterne og som
det ikke er aktuelt � gi en gjestekonto eller lignende f� tilgang til
tjenester ved UiO.

Backenden skal v�re cerebrum, og detaljer for den l�sningen finnes i et annet
dokument. Da vi allerede har et webgrensesnitt til cerebrum som heter
brukerinfo kan virthome ta det som et utgangspunkt.

M�let er � gjenbruke s� mye av brukerinfo-kodebasen som mulig, og kun legge
til funksjonalitet som ikke n� ligger i brukerinfo. Brukerinfo takler allerede
kommunikasjon med en cerebrum-base via en bofhd.

Funksjonalitet
==================
Brukergrensesnittet skal brukes av to forskjellige typer brukere som skal bli
presentert med forskjellige valg. Den ene gruppen er brukere uten f�derert
tilknytning og den andre er for de som har en f�derert tilknytning.

F�dererte brukere skal kunne:

  * Logge inn via FEIDE
  * Opprette grupper
  * Slette grupper de er eier for
  * Invitere en annen f�derert bruker til � bli eier av en gruppe de eier ved bruk av e-postadresse
  * Invitere uf�dererte og f�dererte brukere inn i grupper ved hjelp av en e-postadresse
  * Fjerne brukere fra grupper
  * Legge til f�dererte moderatorer til grupper de er eier av
  * Fjerne moderatorer fra grupper de er eier av
  * Bli med i grupper etter invitasjon

Uf�dererte brukere skal kunne:

  * Registrere ny bruker kun etter invitasjon
  * Endre passord
  * Vise reglement
  * Vise oversikt over gruppemedlemskap
  * Godta � bli medlem av ny gruppe
  * Endre e-postadresse
  * Endre navnet sitt
  * Avvikle bruker

Implementasjon
================

Sider
=======
F�lgende websider skal kunne vises

Felles
-------

Forside
""""""""
Her skal det v�re info om tjenesten og info som gj�r at man kan forst�
de to valgene man f�r om � logge seg inn som enten f�derert bruker eller
uf�derert bruker. 

Invitasjon
"""""""""""
N�r man blir invitert til en gruppe f�r man en e-post med en link som
inneholder en n�kkel som gir tilgang til gruppen. F�lger man den linken
kommer man til en side som ligner p� forsiden, med valg om man er f�derert
eller ekstern bruker samt et ekstra valg for � registrere seg selv.

Er man eksisterende bruker og f�lger en av de to linkene vil man komme til
innloggingssiden for den typen brukere og vil etter innlogging
bli meldt inn i gruppen.

Velger man � registrere seg vil man bli sendt til en egen registreringsside.

F�dererte brukere
--------------------

Feide-innlogging
"""""""""""""""""""
Trykker brukeren p� feide-innloggingslinken som er p� forsiden vil brukeren
bli sendt rett til feide sin side. Etter vellykket p�logging vil brukeren bli
videresendt til denne siden, som vil lagre info om brukeren som vi f�r fra feide og opprette en session
mot bofhd. Hvis brukeren ikke finnes i brukerdatabasen vil den automatisk bli
opprettet. Brukeren blir s� automatisk bli videresendt til hovedsiden for
f�dererte brukere.

Hovedside (f�dererte brukere)
""""""""""""""""""""""""""""""
Oversiktsside med info om hvilke data vi har lagret om brukeren, samt en link
til gruppesiden.

Grupper
""""""""""""
Vise liste over alle grupper brukeren er eier av, er moderator av eller er
medlem av. Det skal v�re en link p� hver gruppe til en side med mer info om
gruppen for de gruppene brukeren enten er eier eller moderator av.

Gruppeside
"""""""""""""""
En side per gruppe, som er linket opp fra "Your groups". Den skal inneholde
info om hvem som er medlem i gruppen og mulighet for � melde dem ut.
Det skal v�re mulig � legge til brukere som medlemmer av gruppen, og det gj�res
kun ved hjelp av e-postadresser.

Det skal ogs� v�re et valg for � legge ned gruppen. Da vil alle brukerene bli meldt
av gruppen og gruppen vil bli satt inaktiv.

Uf�dererte brukere
---------------------

Innlogging
"""""""""""
Innloggingssiden for uf�dererte brukere kan se identisk ut som dagens
brukerinfo-innlogging, og bruke de samme mekanismene.

Hovedside (uf�dererte brukere)
"""""""""""""""""""""""""""""""
Oversiktsside med linker til account og groups-siden.

Account
"""""""""""""""
Skal vise informasjon som er registrert om brukeren:

* e-postadresse
* Navn

Siden skal ogs� gi brukeren mulighet til � endre e-postadressen, navnet
og passordet i tillegg gi muligheten for � slette kontoen. (I praksis
sette den innaktiv)

N�r brukeren skal foreta et passordbytte m� brukeren oppgi n�v�rende
passord, samt nytt passord to ganger. Dette er for � hindre at det nye
passordet blir feilstavet.

Groups
""""""""""""
Vise liste over alle grupper brukeren er medlem av med en beskrivelse av
gruppene. Det skal v�re mulig for brukeren � melde seg ut av enkeltgrupper.


Registreringsside
""""""""""""""""""
Her kommer man etter � ha blitt invitert til en gruppe og man ikke har
en konto enda.
Her m� man oppgi �nsket brukernavn og passord, samt godta reglementet.

Glemt passord
""""""""""""""
P� denne siden kan en bruker som har glemt passordet sitt skrive inn
brukernavnet sitt. Vi vil da sende ut en e-post til den registrerte
e-postadressen for den kontoen med en link til en side hvor brukeren kan
sette et nytt passord.

Registrering
""""""""""""""
Her vil brukeren trenge � fylle ut navn, �nsket brukernavn og �nsket passord.
Siden vi alt har en verifisert e-postadresse trenger vi ikke sp�rre om det.
Hvis brukeren heller vil ha en annen e-postadresse assosiert med kontoen
kan den enkelt byttes senere.

Etter oppretting
""""""""""""""""
Infoside som sier at kontoen er opprettet og at det skal fungere
� logge inn p� tjenesten de har blitt invitert til innen f� minutter.
Det skal ogs� v�re en link til tjenesten og en link til innloggingssiden
til virthome.

Token-verifisering
""""""""""""""""""
Her blir den oppgitte tokenen verifisert mot det vi har lagret og hvis den
stemmer blir e-postadressen verifisert.
