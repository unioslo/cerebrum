/*

Konvensjoner:

 * Forsøker å følge ANSI SQL ('92, uten at jeg helt vet forskjellen på
   denne og '99); dette betyr f.eks. at "CHAR VARYING" brukes i stedet
   for Oracle-datatypen "VARCHAR2", selv om begge disse er
   implementert identisk i Oracle.

 * Kolonner som er hele primærnøkkelen i en tabell, har ofte samme
   navn som tabellen + suffikset "_key".  Kun kolonner som er hele
   primærnøkkelen i tabellen sin har dette suffikset.

 * Når det refereres til en _key-kolonne har kolonnen som inneholder
   referansen altså IKKE navn med suffiks _key (da referanse-kolonnen
   ikke alene er primærnøkkel i tabellen det refereres fra).

 * Alle _key-kolonner bruker type NUMERIC(12,0), altså et heltall med
   maks 12 sifre.

 * For alle tabeller med en _key-kolonne finnes det en sekvens med
   samme navn som _key-kolonnen.  Ved innlegging av nye data i en slik
   tabell skal _key-kolonnen få sin verdi hentet fra denne
   sekvensen.NEXTVAL (for å unngå race conditions).

 * Vi benytter ikke cascading deletes, da dette vil være lite
   kompatibelt med at ymse personer "fikser litt" direkte i SQL.

*/

/***********************************************************************
   Tables for defining user accounts.
 ***********************************************************************/

/*

Data assosiert direkte med en enkelt konto:

 * Eier							== 1

   Kontoen _må_ ha en eier; dette kan enten være en
   person, eller en IT-gruppe (det siste kun for
   upersonlige konti, siden disse ikke eies av noen
   person :-).

 * Kontotype						1..N

   Kontotype bestemmes av et sett med affiliations.
   Alle disse må tilhøre den samme eieren (person
   eller IT-gruppe), slik at en konto kun kan ha
   typer avledet av sin egen eier.

   For upersonlige konti (som altså eies av en
   gruppe) må det settes nøyaktig en konto-type.

 * Brukernavn						1..N

   NoTuR vil, så vidt jeg har skjønt, at vi skal ta
   høyde for følgende rariteter:

   * Enhver konto får tildelt minst ett
     "hjemme"-brukernavn ved opprettelse.  Dette
     brukernavnet er til bruk internt på brukerens
     egen institusjon.

   * Internt på brukerens egen institusjon (altså
     _ikke_ i NoTuR-sammenheng) har
     hjemme-brukernavnet en Unix UID det står
     hjemme-institusjonen helt fritt å velge.

   * I det kontoen skal inn i en NoTuR-sammenheng
     skjer følgende:

     * Kontoen bruker en egen NoTuR-spesifikk Unix
       UID.  Denne er den samme uansett hvilken
       NoTuR-site man opererer på.

     * Kontoen _kan_ måtte bruke andre brukernavn
       for å autentisere seg, da man pre-NoTuR hadde
       opprettet separate sett med brukernavn ved
       hver enkelt NoTuR-site.

    Site	Brukernavn	UID
	"Hjemme"
    UiO		hmeland		29158
	Noen andre ble NoTuR-bruker med
	UiO-brukernavn "hmeland" før hmeland.
    NoTuR/UiO	hameland	51073
	Brukeren som har fått NoTur-brukernavn
	"hmeland" ved UiO har kanskje fått sitt
	ønskede hjemme-brukernavn, "haraldme", på
	NTNU -- men dette var opptatt ved NoTuR/UiO.
    NoTuR/NTNU	hmeland		51073
    NoTuR/UiB
    NoTuR/UiT

   Foreslår at dette løses ved:

   * Mulighet til å reservere brukernavn i kjernen
     (uten at de nødvendigvis er tilknyttet noen
     bruker i ureg2000).

   * Egen modul for NoTuR-opplegget, som sørger for
     å mappe fra "hjemme"-brukernavn til
     NoTuR-brukernavn for riktig site i de
     situasjonenen dette trengs.

 * Autentiseringsdata					0..N

   Om det ikke finnes _noen_ autentiseringsentries
   for en konto, betyr det at man ikke _kan_
   autentisere seg som denne kontoen (og ikke at
   hvem som helst er pre-autentisert som den
   kontoen, i.e. et tomt passord :-).

   En konto kan maks ha en entry
   pr. autentiseringstype.

   type			X.509, MD5, DES
   identifikator	hmeland@foo, NULL, NULL
   private		0x..., NULL, NULL
   public		0x.-.., md5-crypt, DES-crypt

 * Hjemmeområde						0..1
   Noen typer bruker har ikke noe assosiert
   hjemmeområde i det hele tatt, mens i andre
   sammenhenger bør det kunne knyttes separate
   hjemmeområder til hver av de brukernavnene
   kontoen har.

   (I NoTuR-sammenheng kan også samme brukernavn ha
   forskjellig hjemmeområde, alt etter hvilken site
   brukernavnet brukes ved, men dette tas hånd om i
   den NoTuR-spesifikke modulen)

 * Sperring (potensielt flere samtidige, potensielt	0..N
   med forskjellig prioritet)

   Sperring kan også skje på person-nivå (type
   karantene); disse vil da affektere alle kontoene
   personen eier.

   Hver enkelt konto-sperring vil ha tilsvarende
   effekt i _alle_ kontekster der kontoen er kjent.
   Sperring på kontekst-nivå må gjøres ved å fjerne
   aktuell spread.

   TBD: Varighet på sperring og sperre-type.

 * Aktiv/slettet (bør ligge en stund med alle		0..1
   tabell-entries intakt, men flagget som
   slettet, for å lett kunne gjøre restore).

   Dersom vi hadde hatt datostempel for alle
   medlemmers innmeldelse i grupper, kunne dette ha
   blitt implementert som (nok) en gruppe.  Det har
   vi, og vil vi neppe ha, så dermed fremstår
   gruppe-implementasjon ikke som noen lur måte å
   gjøre dette på.

 * Spread (hvilke systemer skal kontoen være		0..N
   kjent i)
   Implementeres vha. grupper med egen nomenklatur
   for gruppenavnene.

   Ved fjerning av spread en spread er det opp til
   hver enkelt eksportmodul å evt. flagge tidspunkt
   for forsvinningen, slik at man unngår "sletting"
   etterfulgt av gjenoppretting (i systemer der
   dette er veldig dumt).

 * Unix UID						0..N

 * Unix primærgruppe					0..N

 * Unix shell						0..N

 * Printerkvote						0..N
   Har/har ikke, ukekvote, maxkvote, semesterkvote.

 * Mailadresser						0..N

 * Plassering i organisasjon (stedkode)			== 1

 * Opprettet av						== 1

   Kontoen som foretok opprettelsen.  Når denne
   brukeren slettes, "arver" kontoen som foretar
   slettingen alle disse opprettelsene.

 * Opprettet dato					== 1

 * Ekspirasjonsdato					0..1

 * LITA(-gruppe) som er ansvarlig kontakt for		== 1
   brukeren

*/


/*	account_type

  Indicate which of the owner's affiliations a specific `account' is
  meant to cover.

  Keeping foreign keys involving person_id against both
  `person_affiliation' and `account' (which in turn has a foreign key
  against `person') ensures that all affiliations connected to a
  specific (personal) user_account belongs to the same person.

*/
CREATE TABLE account_type
(
  person_id	NUMERIC(12,0),
  ou_id		NUMERIC(12,0),
  affiliation	CHAR VARYING(16),
  user_id	NUMERIC(12,0),
  CONSTRAINT account_type_pk
    PRIMARY KEY (person_id, ou_id, affiliation, user_id),
  CONSTRAINT account_type_affiliation
    FOREIGN KEY (person_id, ou_id, affiliation)
    REFERENCES person_affiliation(person_id, ou_id, affiliation),
  CONSTRAINT account_type_user
    FOREIGN KEY (user_id, person_id)
    REFERENCES account(user_id, person_id)
);


/*	account_type_code

  Accounts can be either personal or non-personal.  While the data in
  account_type should be sufficient to identify the type(s) of
  personal accounts, there's still a need to keep track of the various
  kinds of non-personal accounts.

  This table holds code values for these data.  Some examples of code
  values can be "system account", "program account", "group account".

*/
CREATE TABLE account_type_code
(
  code		CHAR VARYING(16)
		CONSTRAINT account_type_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);

/*	account

Konto kan være tilknyttet en person.  Kontoens type indikerer hvorvidt
kontoen kan være upersonlig; integriteten av dette tas hånd om utenfor
SQL.

Konto kan ha forskjellig brukernavn i forskjellige kontekster, men
alle disse skal til enhver tid kunne autentisere seg på (de) samme
måte(ne).

Hvert brukernavn (kontekst?) kan ha tilknyttet et eget hjemmeområde.

 * "User" is an Oracle reserved word, so we're probably better off if
 * we avoid using that as a table or column name.  Besides, "account"
 * probably is the more accurate term anyway.

 np_type: Account type for non-personal accounts.  For personal
          accounts there's a separate user_type table.

 */
CREATE TABLE account
(
  account_id	NUMERIC(12,0)
		CONSTRAINT account_pk PRIMARY KEY,
  owner		NUMERIC(12,0)
		CONSTRAINT account_owner REFERENCES person(person_id),
  group_owner	NUMERIC(12,0)
		CONSTRAINT account_group_owner REFERENCES group_info(group_id),
  np_type	CHAR VARYING(16)
		CONSTRAINT account_np_type REFERENCES account_type_code(code),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  creator	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT account_creator REFERENCES account(account_id),
  expire_date	DATE
		DEFAULT NULL,
  deleted	BOOLEAN
		NOT NULL,
  CONSTRAINT account_one_owner
    CHECK ((owner IS NOT NULL AND np_type IS NULL) OR
	   (group_owner IS NOT NULL AND np_type IS NOT NULL))
);


/*	authentication_code



*/
CREATE TABLE authentication_code
(
  code		CHAR VARYING(16)
		CONSTRAINT authentication_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	account_authentication

 * Keep track of the data needed to authenticate each account.

 TBD:

  * How large should the column method_data be?  Probably at least
    large enough to hold one X.509 certificate (or even several?)

  * Password history (i.e. don't allow recycling of passwords); this
    should probably be implemented as an optional add-on module.

 */
CREATE TABLE account_authentication
(
  account_id	NUMERIC(12,0)
		CONSTRAINT account_authentication_account_id
		  REFERENCES account(account_id),
  method	CHAR VARYING(16)
		CONSTRAINT account_authentication_method
		  REFERENCES authentication_code(code),
  auth_data	CHAR VARYING(1024)
		NOT NULL,
  CONSTRAINT account_auth_pk PRIMARY KEY (account_id, method)
);




/*	reserved_name

  Generic name reservation table.  Value_domain can indicate what kind
  of name (username, groupname, etc.) it is that's being reserved,
  what kind of system the name is being reserved on (Unix, Windows,
  Notes, etc.), and so on -- the exact partitioning of value spaces is
  done in the value_domain_code table.

  TBD: Denne måten å gjøre navne-reservasjon på er såpass generell at
       det blir vanskelig å skrive constraints som sikrer at et navn
       ikke kan finnes både i reservasjons- og definisjons-tabellen
       (altså f.eks. både som reservert og aktivt brukernavn).

       Dersom man skal kunne legge slike skranker i databasen, ender
       man gjerne opp med å måtte ha både reserverte og aktive navn i
       samme tabell, og bruke en egen kolonne i denne tabellen for å
       indikere om det dreier seg om en reservasjon eller
       registrering.  Dette vil igjen føre til nye problemer dersom
       man skal lage foreign keys mot en slik tvetydig navne-kolonne.

*/

CREATE TABLE reserved_name
(
  value_domain	CHAR VARYING(16)
		CONSTRAINT value_domain_code(code),
  name		CHAR VARYING(128),
  why		CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT reserved_name_pk PRIMARY KEY (domain, name)
);


CREATE TABLE account_quarantine
(
  account_id	NUMERIC(12,0)
		CONSTRAINT account_quarantine_account_id
		  REFERENCES account(account_id),

/* TBD: Bør man bruke samme kode-tabell for sperringer av personer og
	brukere? */
  quarantine_type
		CHAR VARYING(16)
		CONSTRAINT account_quarantine_quarantine_type
		  REFERENCES quarantine_code(code),
/* TBD: Hvilke flere attributter trengs knyttet til hver sperring av
	bruker? */
  CONSTRAINT account_quarantine_pk
    PRIMARY KEY (account_id, quarantine_type)
);


CREATE TABLE posix_shell
(
  shell		CHAR VARYING(16)
		CONSTRAINT posix_shell_pk PRIMARY KEY,
  shell_path	CHAR VARYING(64)
		NOT NULL,
  CONSTRAINT posix_shell_path_unique UNIQUE (shell_path)
);


/*	posix_user

  There are several reasons for having separate '*_domain'-columns for
  name, uid and gid:

   * This is necessary if e.g. 'name' should be separately unique in
     NIS domain X and Y, while 'uid' should be unique across both of
     these NIS domains.

   * It's useful to allow separate reservation of user names, uids and
     gids (as these reservations are coupled to the same "value
     domain" names.

  TBD: Holder argumentasjonen over, eller er det bedre å bruke kun en
       kolonne for å indikere verdi-domene for alle tre verdiene?

  'gecos'	For personal users the POSIX gecos field will default
		to the owning persons full name.  The default can be
		overridden by setting this column non-NULL.
		For non-personal users this column must be non-NULL.

*/
CREATE TABLE posix_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT posix_user_account_id
		  REFERENCES account(account_id)
		CONSTRAINT posix_user_pk PRIMARY KEY,
/* TBD: Bør kjernern tillate samme `account' å gi opphav til flere
        `posix_user's, f.eks. dersom man opererer med multiple
        NIS-domener?  Hvis ja: Hva bør da primærnøkkelen for
        posix_user være? */
  name		CHAR VARYING(8)
		NOT NULL,
  name_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_name_domain
		  REFERENCES value_domain_code(code),
  uid		NUMERIC(10,0)
		NOT NULL,
  uid_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_uid_domain
		  REFERENCES value_domain_code(code),
  gid		NUMERIC(10,0)
		NOT NULL,
  gid_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_gid_domain
		  REFERENCES value_domain_code(code),
  gecos		CHAR VARYING(128),
  dir		CHAR VARYING(64)
		NOT NULL,
  shell		CHAR VARYING(16)
		NOT NULL
		CONSTRAINT posix_user_shell REFERENCES posix_shell(shell),
  CONSTRAINT posix_user_name_unique UNIQUE(name, name_domain),
  CONSTRAINT posix_user_uid_unique UNIQUE(uid, uid_domain),
  CONSTRAINT posix_user_gid_unique UNIQUE(gid, gid_domain)
);


/*	notur_user



*/
CREATE TABLE notur_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT notur_user_account_id
		  REFERENCES posix_user(account_id)
		CONSTRAINT notur_user_pk PRIMARY KEY,
  notur_uid	NUMERIC(10,0)
		NOT NULL,
/* TBD: Trenger vi en egen verdidomene-kolonne for UIDer her?  NoTuR
	spiser jo på en måte av alle de involverte institusjonenes
	egne UID-rom, men har på en annen måte fått tilordnet seg sin
	egen range innenfor hver av disse. */
  uid_domain	CHAR VARYING(16)
		CONSTRAINT notur_user_uid_domain
		  REFERENCES value_domain_code(code)
);


/*	notur_site_user

  'name' and 'dir' defaults to the corresponding values from the
  parent posix_user.

*/
CREATE TABLE notur_site_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT notur_site_user_account_id
		  REFERENCES notur_user(account_id),
  notur_domain	CHAR VARYING(16)
		CONSTRAINT notur_site_user_notur_domain
		  REFERENCES value_domain_code(code),
/* TBD: Vil UNIQUE-constrainten nederst fungere som den skal dersom
	'name' tillates å kunne være NULL? */
  name		CHAR VARYING(8),
  dir		CHAR VARYING(64),
  CONSTRAINT notur_site_user_pk PRIMARY KEY(account_id, notur_domain),
  CONSTRAINT notur_site_user_unique UNIQUE(notur_domain, user_name)
);


/* TBD: Spread for brukere; bør dette implementeres ved hjelp av en
	"REFERENCES account(account_id)"-type tabell, eller som
	separat spread-tabell for hver enkelt variant av bruker det
	finnes andre tabeller for (som f.eks. posix_user)? */


/* TBD: Bør printerkvoter legges på brukere eller personer, eller bør
	man kanskje til og med ha mulighet for å legge innslag begge
	steder (og hvilke konsekvenser får i så fall det for hvordan
	logikken rundt må se ut)? */

CREATE TABLE printer_quota
(
  person_id	NUMERIC(12,0)
		CONSTRAINT printer_quota_person_id
		  REFERENCES person(person_id),
  account_id	NUMERIC(12,0)
		CONSTRAINT printer_quota_account_id
		  REFERENCES account(account_id),
  active	BOOLEAN,
/* TBD: Bør vi splitte ut kolonnene under i en annen tabell, slik at
	det kun blir ett "active"-flagg for å si om en person/bruker
	har aktiv(e) printerkvotesettinger eller ei? */
  value_type	CHAR VARYING(16)
		REFERENCES printer_quota_value_code(code),
  value		NUMERIC(6,0)
		NOT NULL,
  PRIMARY KEY(person_id, value_type)
/* eller */
  PRIMARY KEY(account_id, value_type)
);


CREATE TABLE mail_domain
(
  domain_name	CHAR VARYING(128),

/* TBD: Ønsker å kunne legge inn innslagg her om domener uten at det
	nødvendigvis eksporteres noe data om dem til epostsystemet.
	Er det nødvendig med muligheter for registrering av flere
	opplysninger rundt dette, så som "starttidspunkt som lokalt
	domene", "tidspunkt for når domenet sluttet/vil slutte å være
	lokalt domene", etc.? */
  local		BOOLEAN
		NOT NULL,
  description	CHAR VARYING(512),
  PRIMARY KEY domain_name
);

/* TBD: Flere tabeller om mail. */
