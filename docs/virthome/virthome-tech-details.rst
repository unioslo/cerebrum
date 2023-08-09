=========
VirtHome 
=========

.. admonition:: Needs review

   This is an old document, some of the instructions may be out of date.

.. contents:: Innholdsfortegnelse



Innledning
============
Dette dokumentet beskriver de tekniske detaljene på Cerebrum-siden knyttet til
implementasjonen av VirtHome-funksjonalitet.

Hovedføringen for implementasjonen er å gjenbruke så mye av Cerebrum-kodebasen
som overhodet mulig. Der hvor databaseskjema ikke tilbyr de nødvendige
skrankene, velger vi heller å flytte håndteringen av skrankene inn i koden,
heller en å lage nye moduler.



VirtHome-entiteter
===================
Det er tre logiske enheter som utpeker seg som entiteter i VirtHome -- brukere
uten føderert tilknytning (VirtAccount), brukere med føderert tilknytning
(FEDAccount) og grupper (VirtGroup) der de to første entitetene kan være
medlemmer. Alle de andre entitetene vi trenger er allerede i Cerebrum-kjernen.

VirtAccounts (VA) er brukere som vi vet minst om, da all informasjon om disse
kommer fra en ikke tiltrodd kilde (det er meningen av folk skal kunne lage
sine egne VirtAccounts uten noe form for verifikasjon av opplysningene). Den
eneste "merkelappen" vi har på disse er e-postadressen.

FEDAccounts (FA) er brukere som stammer fra en tilknyttet institusjon og disse
besitter bl.a. en ID i Feide og antas videre til å være verifiserte (dvs. vi
antar at informasjonen lagret i VirtHome om disse brukere er til å stole på).

VirtGroups (VG) er grupper der begge typer konti kan være medlemmer (og gjerne
innen den samme gruppen).

Det er intet poeng i å finne på nye entiteter i db-skjema, og følgelig lagrer
vi informasjon om begge typer konti i ``code_tables.sql:account_info``, og
informasjon om grupper legges i ``core_tables.sql:group_info``. 


VirtAccount
------------
Selv om vi gjenbruker ``account_info``, må det til en ny entitet i kodebasen
for å støtte visse operasjoner på VirtAccounts. Koden for VirtHome kontotyper
ligger i ``Cerebrum/modules/virthome/VirtAccount.py``. VirtAccount blir
naturlig til egen klasse, ``VirtAccount``. Både ``VirtAccount`` og
``FEDAccount`` (se under) har noen fellestrekk og fellesbaseklassen for disse
arver fra Account. Ideelt sett burde dette ha blitt løst ved å la
``AccountType``, ``AccountHome`` og autentiseringsfunksjonaliteten være
separate mixin-klasser som legges i ``CLASS_ACCOUNT`` ved behov, men det er
dessverre ikke slik. Pga. litt uheldig arverekkefølge til ``Account`` må man
reimplementere en del metoder vi kunne ellers ha greid oss uten. Disse kaster
``NotImplementedError`` dersom de blir brukt (det er ikke meningen at de skal
kunne brukes). 

.. FIXME: Kan vi løse dette mer elegant med metaklasser?

For hver VirtAccount lagrer vi følgende data i Cerebrum:

  * E-postadresse (påkrevd, ikke unik). Denne lagres som egen
    ``contact_info``. Det er ikke noe poeng i å dra inn ``Email``-modulen kun
    for å lagre adressene. 
  * Brukernavn (påkrevd, unik) lagres som egen type ``entity_name``.
  * Opprettelsesdato (påkrevd), lagres i ``account_info``
  * Sluttdato (påkrevd), lagres i ``account_info``. DB-skjema har ikke
    NOT NULL skranken på sluttdato, så dette vil måtte forsikres i koden.
  * Navn på eieren. Denne er valgfri. Et praktisk problem her er at
    ``entity_name`` har en unique-skranke på navn av samme type og kan derfor
    ikke brukes til å lagre eiernavn. Det greieste er å lagre dette som
    entity_contact_info. Ideelt sett burde vi migrere Cerebrum til å bruke
    unike og ikkeunike navn og ha dertil egnede tabeller i db-skjema. Dette
    løses dog ikke av/i VH.
  * Passord. Denne kan lagres i ``account_authentication`` og
    ``password_history``. 
  * Spread til LDAP (og sikkert en del andre). Dette løses enkelt
    vha. ``entity_spread``. 
  * Karantener. Dette løses enkelt vha. ``entity_quarantine``.
  * Traits (litt uklart hvilke traits vi kan trenge akkurat nå, men det
    spiller liten rolle) -- EntityTrait-modulen er veltestet.

Siden vi ikke kan stole på navn som folk skriver selv om seg selv, må vi ha et
system for å merke alle navn på VA-eiere slik at det fremgår tydelig at
informasjonen ikke er fra en tiltrodd kilde. Merk at dette gjelder kun
eksporten til andre systemer (slik som LDAP). Dvs. at "Schnappi das Krokodil"
vil måtte merkes på en eller annen måte som tydeliggjør at det navnet ikke
stammer fra en tiltrodd kilde, slik som f.eks. "Schnappi das Krokodil
(unverified)" **kun** ved eksport til andre systemer; internt i Cerebrum
forblir navnet uendret (internt i Cerebrum vet man til enhver tid ut fra
kontotypen om informasjonen om kontoen er fra en tiltrodd kilde).

Videre er det slik at ``account_info`` alltid har en eier, som er enten en
account eller en gruppe. Siden vi ikke har en entitet i Cerebrum som eier en
VirtAccount, er det naturlig å la "systemet" eie VAs. I dette tilfellet blir
det ``cereconf.INITIAL_GROUPNAME/INITIAL_ACCOUNTNAME`` som eier alle VAs.

Navn på VAs (egentlig på både VA og FA) i VirtHome har en indre struktur --
"<name>@<realm>". For VirtAccount spesifikt er <realm> fastsatt
(``cereconf.VIRTHOME_REALM`` inneholder realm) -- alle VA-brukernavn er på
formen "<noe>@VH". "<noe>"-delen er opptil hver enkel bruker å bestemme,
såfremt det resulterende brukernavnet ikke er allerede tatt.
``VirtAccount:illegal_name()`` sjekker at det blir håndtert (vi har ingen
db-skjemaskranker på dette punktet).

Et vesentlig punkt knyttet til alle VA-er er at en rekke kommandoer (også
opprettelse) krever et bekreftelsessteg. Dette er beskrevet senere i
`Bofhd-kommunikasjon`_. 

Det er litt uklart om VA må kunne slettes komplett fra Cerebrum, dvs. om vi
trenger en passende ``nuke()``-funksjon. Imidlertid VA-er som ikke er
bekreftet (se avsnittet om opprettelse) må kunne slettes. Relatert til dette,
``is_active()`` for en VA må ta hensyn til expire_date OG til hvorvidt kontoen
er blitt bekreftet.

En VA opprettes med en gang i VH, etter at brukeren ba om opprettelse av en ny
VA, men settes med en gang i karantene, slik at nye brukere er nødt til å
bekrefte opprettelsen før kontoen tas i bruk. I det en slik bekreftelse
kommer, fjernes karantenen og VA gis spread til LDAP.

For VA tar Cerebrum vare på passord. Vi trenger å definere hva et gyldig
passord er og sjekket det i API-et (``PasswordChecker``-rammeverket er på
plass alt). Siden Cerebrum har oversikt over passord, kan vi autentisere
VA-brukere ved innlogging gjennom bofhd/cerebrum.

For selve passordkravet er det enkleste å legge seg på passphrases. Vi krever
at passordet tilfredstiller samtlige av følgende krav:

  - Minst 12 tegn.
  - Ingen repetisjon på 4 eller flere tegn. ('aaaa' -- ikke tillatt)
  - Ingen sekvenser på 4 tegn eller lengre ('1234' og 'qwerty' -- ikke
    tillatt)
  - Passord er fra alfabetet [a-zA-Z0-9] + et par spesialtegn.

.. FIXME det er potensielt aktuelt å tillate kortere passord, MEN da må vi har
   mer strikte sjekker når passordene er i 8-12 tegn i lengde.

Vi krever opprettelses- og expire-dato for alle VA-er. DB-skjema støtter ikke
dette kravet, så dette må sjekkes i API-et. I utgangspunktet antar vi at en
konto er ekspirert etter ett år. Uansett er expire_date aldri NULL/None.

For å logge seg inn i VirtHome skal folk bruke brukernavn. E-post, derimot, er
den kommunikasjonskanalen som VH har til hver enkel bruker (det er i praksis
den eneste måten systemet kan kommunisere med brukeren på).

Hver VA blir nødt til å bekrefte at kontoen er i bruk med jevne mellomrom. Det
enkleste er å gjøre dette ifm. passordbytte som skjer hver 6. måned. Som et
ledd i oppryddingsrutinene, vil man sende rutinemessige varsler om
passordbytte (ikke ulik slik det gjøre ved UiO i dag). Det er foreløpig uklart
hva som skjer med VA, dersom brukeren unnlater å bytte passordet (VA skal få
karantene og skal sperres fra eksport til eksterne systemer (f.eks. LDAP), men
skal vi slette brukeren helt? Gjøre noe annet?)

Et annet åpent spørsmål er hvordan selve passordbytte skal forløpe seg. Vi må
hindre at uvedkommende DoS-er en VA, samtidig som det skal være mulig, etter å
ha glemt et passord, å få gjenopprettet tilgangen til kontoen.



FEDAccount
-----------
Det er en del felles trekk mellom FA og VA, så de begge bruker
``account_info`` og arver fra samme baseklasse. Likevel er det noen
forskjeller, slik at hver av disse får egen klasse.

For hver FEDAccount lagrer vi følgende data i Cerebrum:

  * E-postadresse (påkrevd, ikke unik). Denne lagres som egen
    ``contact_info``. Det er ikke noe poeng i å dra inn ``Email``-modulen kun
    for å lagre adressene. 
  * Brukernavn (påkrevd, unik) lagres som egen type ``entity_name``.
  * Opprettelsesdato (påkrevd), lagres i ``account_info``
  * Sluttdato (påkrevd), lagres i ``account_info``. DB-skjema har ikke
    NOT NULL skranken på sluttdato, så dette vil måtte forsikres i koden.
  * Navn på eieren. Denne er valgfri. Et praktisk problem her er at
    ``entity_name`` har en unique-skranke på navn av samme type. I dette
    tilfellet blir vi nødt til å utvide skjema med en ny tabell for å lagre
    ikke-unike navn av bestemt type -- ``entity_non_unique_name``.
  * Spread til LDAP (og sikkert en del andre). Dette løses enkelt
    vha. ``entity_spread``. 
  * Karantener. Dette løses enkelt vha. ``entity_quarantine``.
  * Traits (litt uklart hvilken traits vi kan trenge akkurat nå, men det
    spiller liten rolle) -- EntityTrait-modulen er veltestet.

Da data for FA antas til å stamme fra en tiltrodd kilde, gjøres det ingen
manipulasjoner med eiernavn for FA-er ved eksport til eksterne systemer slik
det gjøres med VA. Videre er det også slik at siden denne tiltrodde kilden er
autoritativ for informasjonen om en FA, oppdateres data om FA-en i VH hver
gang vedkommende logger seg inn i VH (slik at vi f.eks. automatisk oppdaterer
eiernavnet for kontoen, dersom navnet endrer seg i Feide).

I likhet med VA-er, eies FA-er av systemet
(``cereconf.INITIAL_GROUPNAME/ACCOUNTNAME``).

I likhet med VA-er, er navn på FA-ene strukturert som
``<name>@<realm>``. Imidlertid får hver tilknyttet institusjon egen "<realm>"
(dette sjekkes i API-et, siden db-skjema ikke har den type sjekke innebygd).

En viktig forskjell mellom VA og FA er autentisering. VirtHome lagrer ikke
passord for FA-ene -- disse skal autentiseres eksternt, heller enn gjennom
Cerebrum. Dette reiser en del andre problemstillingene, siden f.eks. bofhd
(som er (om enn i en modifisert utgave og bak en web-applikasjon) det
verktøyet vi skal bruke for å tilby et grensesnitt til brukere) alltid har
gjort autentiseringen selv. Mer om dette i `Innlogging`_. API-et bør har en
sperre for å sette passord på FA-ene.

I likhet med FA får VA-brukere LDAP-spread etter første innlogging.

Når det gjelder expire-dato, er det en utfordring knyttet til FA-er, siden de
ikke har noe "bytt-passord-i-VH"-funksjon som man kan bruke som bekreftelse på
at kontoen fremdeles er i bruk. Det enkleste er å sende ut bekreftelsese-post
(ikke ulik passordvarsling) og be brukeren bekrefte bruken ved å følge en
link.

Siden FA og VA deler den samme tabellen (``account_info``), og vi trenger å
skille mellom disse to typene, introduseres et par nye konstanter (for å
skille på ``account_info.np_type``) -- ``virtaccount_type`` og
``fedaccount_type``.


VirtGroup
----------
Den tredje og siste VirtHome-entiteten er VirtGroup -- en gruppe der
medlemmene er VA-er og FA-er. VG er ganske like gruppene i Cerebrum.

Alle VG-er har en eier, en creator og fra 0 til flere moderatorer. Det er kun
FA-er som kan være eier/creator/moderator; VA-er kan kun være medlemmer.

For hver VirtGroup lagrer vi følgende data i Cerebrum:

  * Gruppenavn (påkrevd) lagres i ``entity_name``.
  * Gruppebeskrivelse (påkrevd) lagres i ``group_info``.
  * Eier (påkrevd) lagres i bofhd_auth*. At eieren er påkrevd sikres via
    bofhd.
  * Moderatorne for gruppen (valgfri), lagres i bofhd_auth*. 
  * Spreads lagres i ``entity_spread`` (f.eks. spread til LDAP).
  * En gruppe"ressurs" (URL, foreløpig) som er ment til å peke på
    ekistensgrunnlaget for gruppen. F.eks. hvis gruppen representerer hvem som
    skal få lov til å kommentere på en spesiell blogg, så er ressursen URL til
    denne bloggen. Dette lagres som ``entity_contact_info``.

.. FIXME: Muligens "display name" av noe slag, altså framvisningsnavn, dersom
   gruppenavn er laget for datamaskiner heller enn mennesker. Det er blitt
   foreslått å lage gruppenavn på formen "urn:mace:uio.no:...", men dette er
   ikke spesielt menneskevennlig.

.. FIXME: Kanskje modereringsstatus for gruppen. Litt uklart om 1) det er
   overhodet nødvendig (0 moderatorer == ikke-moderert gruppe) 2) hvordan
   det skal implementeres, om overhodet (antageligvis en trait).

Både VA og FA kan være medlemmer i den samme gruppen (vi burde dog legge inn
sperre for alle andre account_typer i API-et). Dog, det er kun FA som kan være
eiere og moderatorer av en VG. Igjen, dette sjekkes i API-et (siden db-skjema
ikke støtter det).

Vi har allerede et opplegg for å uttrykke eierskap og moderatorstatus gjennom
rettighetsrammeverket til bofhd (``bofhd_auth.sql``). Vi kan endre eierskap og
moderasjonsstatus på samme måte som rettighetene tildeles i dag, si, ved UiO.

Gruppenavn i virthome må ha en realm, på samme måte som VA sine navn -- alle
grupper kommer til å hete "<noe>@VH", der <noe> er opptil FA-en som lager
gruppen (såfremt gruppenavnet ikke er tatt allerede).

Det skal til enhver tid være eksakt 1 eier av en VG. Eierskapet kan imidlertid
overdras til en annen bruker. Denne overdragelsen skjer gjennom et
bekreftelsessteg (f.eks. på samme måte som registrering av nye VA-er). Det er
kun nåværende eier som kan overdra eierskapet. Tilsvarende bekreftelse kreves
når eier eller moderator ønsker å melde en annen bruker som moderator.

Enhver bruker kan meldes inn i en gruppe (det kreves aktivt samtykke fra
brukeren, dog). Brukeren selv, gruppeeier og gruppemoderator kan melde en
bruker ut av gruppen. Når brukeren meldes ut av gruppen av
gruppeeier/moderator, skjer dette i stillhet for brukeren. Fjerning av
medlemmer blir registrert i Cerebrum sitt change_log, så vi har en oversikt
over hvilken konto meldte en gitt konto ut av en gruppe til enhver tid.

.. FIXME: Det er også blitt foreslått at vi burde merke på en eller annen måte
   at gruppen har medlemmer fra usikre (VA) og tiltrodde kilder (FA), dog det 
   er kanskje mer et spørsmål for presentasjonslaget.

Gruppemedlemskap uttrykkes gjennom ``group_member``, hvor det er helt
uproblematisk å blande sammen VA og FA innad samme gruppe.



Skjemautvidelsene
==================
Det er nødvendig med et lite supplement til Cerebrum-skjema. Vi trenger en
unik identifikator for utestående change_log requests, og denne
identifikatoren bør være passe stor/tilfeldig (mao ikke en entity_id eller
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
som må introduseres i bofhd. 

Den overordnede oversikten er angitt i ``over-communication-sketch.dia``. 

Den spesifikk kommandosekvensen for de operasjonene som krever autorisasjon er
skissert i ``command-with-login.dia``. 


Innlogging
-----------
Bofhd er kodet slik at alle brukere må autentisere seg før de kjører noen
kommandoer og privilegiene på alle de påfølgende kommandoene sjekkes mot
sesjon-ID-en gitt ved innlogging. Denne tilnærmingen er ikke så gunstig for
VH: FA-er autentiserer seg mot Feide og VirtHome lagrer ikke deres passord
engang. Mao. tillittskjeden må utvides og bofhd må stole på at
web-applikasjonen (web-frontend) har autentisert brukeren.

Imidlertid er problemet fortsatt der -- bofhd kan ikke bare kjøre vilkårlige
kommandoer sendt av en eller annen FA/VA på den andre enden av
oppkoblingen. Det foreslås dermed å autentisere samt utføre kommandoene på
følgende måte:

  #. VA-er logger seg inn direkte i VH sin bofhd. Her kreves det ingen
     spesialtilpasninger.

For FA-er, derimot, ser prosessen slik ut:

  #. Web-frontenden sørger for å redirecte brukeren til rett
     autentiseringstjeneste (Moria? LDAP?) og får tilbake en bekreftelse på at
     brukeren er autentisert [#auth1]_.
  #. Deretter logger web-frontenden seg mot bofhd som web-applikasjon. Det må
     opprettes (på forhånd) egen bruker til web-applikasjonen med visse
     rettigheter i bofhd. Brukernavn/passord må skrives (i klartekst) i en
     passende fil på maskinen som kjører web-applikasjonen. Tilgangen til
     denne filen må ikke gis til noen andre enn den brukeren som
     web-applikasjonen kjører som. Tanken med denne er å kreve at den som
     kobler seg mot bofhd kjenner til en eller annen hemmelig nøkkel, slik at
     ikke hvem som helst skal kunne logge seg inn mot bofhd, enda bofhd står
     på et nett med begrenset tilgang (forhåpentligvis).
  #. Deretter gjør web-frontend en "su <bruker>" kommando, for å registrere at
     alle de påfølgende kommandoene kjøres som "<bruker>". Mao, bofhd
     tilordner den eksisterende web-frontend sesjon til en annen bruker. Det er
     viktig å begrense mengden av brukere som får lov til å bytte eierskapet
     til sesjonen mot bofhd (i prinsippet er det kun web-applikasjonen som
     skal trenge det).
  #. Deretter kan kommandoene fra brukeren sendes via web-applikasjonen til
     bofhd (slik det er i dag med jbofh, cweb, osv.).

Siden kommunikasjonen mellom wep-applikasjonen foregår over HTTPS, er det
ingen mulighet for å avlytte sesjon-ID-en og misbruke den. Svakheten i denne
løsningen er at web-applikasjonen må ha tilgang til sitt eget
brukernavn/passord i klartekst. Blir web-applikasjonen eller web-tjeneren
kompromittert, vil angriperen kunne endre sesjonseierskap (og dermed
rettighetene knyttet til sesjonen) til hvilken som helst bruker i VirtHome.

For å oppsummere, dagens ordning med "innlogging før kommando" består, men i
en noe endret form.  

En annen viktig del av saken er at i VirtHome må det finnes en rekke
kommandoer som ikke krever innlogging fra brukernes side (registrering av en
ny VA, det å bekrefte en forespørsel sendt per e-post). Per design er det slik
at hvem som helst skal kunne opprette en ny VA uten noe tidligere tilknytningn
til VirtHome. Dette betyr at web-applikasjonen må kunne ikke bare gjøre "su
<bruker>" men også videreformidle slike
kommandoer-fra-brukere-uten-autentisering. Naturligvis vil web-applikasjonen
fremdeles måtte logge seg inn til bofhd og så sende en "opprett en ny
VA"-kommando til bofhd (som seg selv, heller enn på vegne av en annen bruker).

.. [#auth1] Akkurat hvordan dette gjennomføres praktisk er ikke så veldig
            interessant her. Vi bare antar at det finnes en tjeneste som
            web-applikasjonen kan bruke for å få en bekreftelse på at brukeren
            som logger seg inn er den vedkommende påstår å være.


Hendelsesforløp
-----------------
La oss se på hendelsesforløp i følgende situasjoner knyttet til bofhd / dens
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

Fra det tidspunktet av er VA autentisert og kan utføre kommandoer med dertil
passende rettigheter/tilganger.

Innlogging av en FA
~~~~~~~~~~~~~~~~~~~~~
  #. Brukeren velger den websiden der h*n kan logge seg inn som feide-bruker.
  #. Brukeren autentiserer seg mot feide
  #. webapp får en datablobb fra brukeren/feide
  #. webapp logger seg inn i bofhd med eget brukernavn/passord
  #. webapp kaller ``user_fedaccount_login`` med parametre fra blobben
     (brukernavn, e-post, personnavn. Vi krever minst disse 3)
  #. dersom det brukernavnet ikke finnes i virthome, opprettes det av bofhd.
  #. deretter tilordner bofhd sesjonen til den aktuelle brukeren (webapp
     eier ikke lenger sesjonen og alle kommandoer utføres med privilegiene til
     brukeren).

Gruppeinvitasjon
~~~~~~~~~~~~~~~~~~
Fødererte brukere kan opprette grupper i virthome (f.eks. med det formålet å
styre tilgangen til blogg/wiki). En FA kan invitere i en gruppe som
vedkommende eier/modererer andre brukere. Siden de inviterte er ikke
nødvendigvis registrert i virthome, baseres invitasjonsutsendelsen på
e-postadresser.

Hendelsesforløpet blir da:

   #. En FA logger seg inn (beskrevet tidligere)
   #. FA velger ut gruppen og e-postadressene som skal inviteres til den. 
   #. For hver e-postadresse lages det en invitasjon i bofhd (webapp kaller
      ``bofhd_group_invite``)
   #. For hver slik invitasjon, lages det en bofhd_request og webappen får
      tilbake et engangspassord (OTP)
   #. Webapp sender e-post med invitasjonen til den gitte e-postadressen der
      OTP er bakt inn.
   #. E-postmottageren følger linken med OTP bakt inn.

Deretter er det flere mulige scenarioer: den inviterte er en FA, er en VA som
alt finnes i virthome eller er en VA som ikke er registrert i
virthome. Hendelsesforløpene blir da hhv:

  * For en FA:

     #. logge seg inn i virthome (slik beskrevet tidligere)
     #. ``user_confirm_request(OTP)`` som vil da melde FA-en (som eier
        bofhd-sesjonen) inn i den gruppen som er assosiert med OTP.

  * For en VA som finnes:

     #. logge seg inn i virthome (slik beskrevet tidligere)
     #. ``user_confirm_request(OTP)`` på samme måte som for FA.

  * For en VA som ikke finnes:

     #. webapp finner ut hvilken e-postadresse OTP ble sendt til
        (``request_parameters``)
     #. Brukeren får beskjed om å registrere seg, hvor vedkommende får fylle
        ut alle felt, bortsett fra e-post.
     #. Brukeren registrerer seg. På dette tidspunkt er det ikke nødvendig å
        bekrefte e-postadressen (vi vet jo hvilken e-postadresse en gitt
        invitasjon er blitt sendt til)
     #. webappen kaller ``user_confirm_request(OTP)`` på samme måte som for
        FA for å melde den nye VA inn i gruppen.

   Legg merke til at dette er den eneste måten som nye VA-er kan oppstå i
   VirtHome. Det skal ikke finnes en annen måte å få opprettet VA-er.

Passordgjenopprettelse
~~~~~~~~~~~~~~~~~~~~~~~
Naturlig nok må vi ha et opplegg for passordgjenopprettelse. Ideen er at
VA-brukerne som glemmer innloggingspassordet i VH skal kunne få et nytt
passord. Vi må sørge for at eksisterende brukere ikke kan bare bli DoS-et ut
av VH, og derfor foregår passordbytte først etter at vi får bekreftet at en
gitt e-postadresse virkelig *ønsker* å få passordet byttet. 

For ordens skyld, passordet blir gjenopprettet i den forstand at det gamle
passordet blir utlevert i klartekst; vi lager et nytt passord (når det blir
aktuelt) og setter det. Brukeren får så et nytt passord og kan da bytte
det. Dersom vi lager tilstrekkelig kjipe automatiske passord, blir folk
tvunget til å bytte det autogenererte passordet med en gang selv :)

Da foregår situasjonen slik:

  #. Brukeren kommer til en webside der vedkommende fyller ut e-postadresse OG
     brukernavn og trykker på "recover my password"
  #. webapp logger seg inn i bofhd (som seg selv) og kaller
     ``user_recover_password(email, uname)``
  #. bofhd lager en request, der email/uname noteres og returnerer OTP til
     webapp. 
  #. webapp sender en e-post til den aktuelle e-postadressen med en link
     tilbake med OTP.
  #. Brukeren trykker på linken og kommer til en side der vedkommende fyller
     ut det nye passordet sitt.
  #. webapp logger seg inn som seg selv og kjører
     ``user_confirm_request(OTP, nytt passord)``. 
  #. bofhd sjekker og setter det nye passordet.


Kommandoer som krever bekreftelse
----------------------------------
En rekke kommandoer i VirtHome vil kreve et bekreftelsessteg, siden en
trykkfeil vil potensielt kunne ødelegge for brukeren eller skape merarbeid for
oss. Dette gjelder endring av e-post for VA-er, gruppeinvitasjon, overdragelse
av eierskap til en gruppe, osv.

I utgangspunktet var planen å bruke traits til dette. Imidlertid kan det være
mye tilstandsinformasjon knyttet til en bekreftelse, og da er det enklere å
bruke ``change_log`` til formålet (traits har ikke en CLOB/BLOB knyttet til
seg som man kan stappe parametre i, change_log har det -- ``change_params``;
vi trenger nok å kunne lagre en del tilstandsinformasjon knyttet til en slik
bekreftelseshendelse).

Så, gitt en handling som krever en bekreftelse, der handlingen har en rekke
parametre P, vil følgende skje i dag:

  #. Man lager en unik request-id, som skal identifiseres handlingen
     entydig. Vi bruker UUID4, men hva som helst langt og tilfeldig
     duger. 
  #. Parametre P til handlingen samles i en dict
  #. Det lages en ny change_log event, som:

       * ... har ``change_params`` satt til ``pickle.dumps(P)`` (mao. den er satt
         til den picklede parameterdict-en (ja, det er brudd på 1NF, og det er
         trist, men slik er det).
       * ... har ``subject_entity`` pekende på den entiteten som bekreftelsen
         gjelder.
       * ... er forbundet med den unike request-id-en. 

     Den siste biten er nødvendig for å kunne finne igjen en spesifikk
     change_log event senere.
  #. Den unike request-iden returneres tilbake til webapplikasjonen.

.. (FIXME: vi trenger en vurdering av sikkerhetssjefen på akkurat dette).

Planen er da som følgende. En bruker utfører en handling i webapp-en som
krever bekreftelse. webapp-en kaller en kommando i bofhd som lager en slik
bekreftelse (i change_log) og returnerer request-id til webappen. webappen
sender en e-post til brukeren der det er bakt inn en URL tilbake til virthome
med request-id som en parameter. Når brukeren får e-post og trykker på linken
i e-posten, kaller webapp en kommando i bofhd med request-id-en (tatt fra
HTTP-parameteren/URL-en) som argument. bofhd da utfører den aktuelle
handlingen, og sletter change_log-eventen.

Det alene er ikke tilstrekkelig, siden vi må rydde opp i events som ikke er
blitt bekreftet. ``reaper.py`` er ment til det formålet (siden alle
``change_log``-hendelser har et tidsstempel). Det er slik at vi etterstreber å
ikke endre tilstanden i VH før en hendelse er blitt bekreftet; f.eks. gitt en
forespørsel om å bytte e-post for en VA, eksisterer VA-en med den gamle
e-postadressen helt fram til bekreftelsesmeldingen mottas (e-postadressen
skiftes først da).


Rettighetsforvaltning i bofhd
------------------------------
Per i dag er de aller fleste (alle?) kommandoer i bofhd implementert slik at
det sjekkes om brukeren som utfører kommandoen har rett til å utføre
den. Denne ordningen kan gjerne bestå i VirtHome-utgaven også. Imidlertid er
det slik at noen av kommandoene skal kunne kjøres av VirtHome-brukere uten at
de skal trenge å logge seg inn. Alle kommandoene skal formidles via
web-applikasjonen uansett. Dette betyr at for en rekke kommandoer (slik som
opprettelse av nye VA-er), er det web-applikasjonen selv som vil utføre dem
(heller en eller annen spesifikk VA/FA). Rettighetene kan således hektes på
systemkontoen tildelt web-applikasjonen. Eksempelvis vil ikke noen andre
trenge å ha tilgang til opprettelse av virtaccount enn nettopp
web-applikasjonen i VirtHome-bofhd.

Nå er det slik at bofhd er bygget rundt ideen om at enhver kommando (selv en
uten restriksjoner) ikke kan kjøres uten at brukeren er loggen inn. For
virthome passer dette en smule dårlig. Det finnes dog en løsning: kommandoer
som ikke krever innlogging (f.eks. det å lage en ny bruker eller å utføre en
bekreftelse) utføres av web-applikasjonen (som da alltid logger seg in);
kommandoer som utføres av en VA kan utføres etter at vedkommende logget seg
inn (vi har de krypterte passordene i Cerebrum, og autentisering er triviell);
kommandoer som utføres av en FA kan utføres etter at webapp gir beskjed til
bofhd om at brukeren er autentisert. Det siste krever naturligvis at bofhd
stoler på at webapp har rett når den sier at dens sesjon skal byttes til en
annen bruker.
