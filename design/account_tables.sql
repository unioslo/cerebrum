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

 * Aktiv/slettet (bør ligge en stund med alle		0..1
   tabell-entries intakt, men flagget som
   slettet, for å lett kunne gjøre restore).

   Dersom vi hadde hatt datostempel for alle
   medlemmers innmeldelse i grupper, kunne dette ha
   blitt implementert som (nok) en gruppe.  Det har
   vi ikke, og vil nok heller ikke ha, så dermed
   fremstår gruppe-implementasjon ikke som noen lur
   måte å gjøre dette på.

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

   Kontoen som foretok opprettelsen.  Konti som er
   registrert som "oppretter" kan ikke fjernes (men
   kan markeres som inaktive).

 * Opprettet dato					== 1

 * Ekspirasjonsdato					0..1

 * LITA(-gruppe) som er ansvarlig kontakt for		== 1
   brukeren

*/


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
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		NOT NULL
		DEFAULT 'u'
		CONSTRAINT account_entity_type_chk CHECK (entity_type = 'u'),

  account_id	NUMERIC(12,0)
		CONSTRAINT account_pk PRIMARY KEY,
  owner_type	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT account_owner_type_chk
		  CHECK (owner_type IN ('p', 'g')),
  owner		NUMERIC(12,0)
		NOT NULL,
  np_type	CHAR VARYING(16)
		CONSTRAINT account_np_type REFERENCES account_code(code),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  creator	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT account_creator REFERENCES account(account_id),
  expire_date	DATE
		DEFAULT NULL,
  deleted	CHAR(1)
		NOT NULL
		CONSTRAINT account_deleted_bool
		  CHECK (deleted IN ('T', 'F')),
  CONSTRAINT account_entity_id FOREIGN KEY (entity_type, account_id)
    REFERENCES entity_id(entity_type, id),
  CONSTRAINT account_owner FOREIGN KEY (owner_type, owner)
    REFERENCES entity_id(entity_type, id),
  CONSTRAINT account_np_type_chk
    CHECK ((owner_type = 'p' AND np_type IS NULL) OR
	   (owner_type = 'g' AND np_type IS NOT NULL)),
  CONSTRAINT account_id_plus_owner_unique UNIQUE (account_id, owner)
);


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
    REFERENCES account(account_id, owner)
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

  Keep track of the data needed to authenticate each account.

  TBD:

   * `method_data' is currently as large as Oracle will allow a "CHAR
     VARYING" column to be.  Is that large enough, or should we use a
     completely different data type?  The column should probably be at
     least large enough to hold one X.509 certificate (or maybe even
     several).

   * Should the auth_data column be split into multiple columns,
     e.g. for "private" and "public" data?

   * Password history (i.e. don't allow recycling of passwords); this
     should be implemented as an optional add-on module.

*/
CREATE TABLE account_authentication
(
  account_id	NUMERIC(12,0)
		CONSTRAINT account_authentication_account_id
		  REFERENCES account(account_id),
  method	CHAR VARYING(16)
		CONSTRAINT account_authentication_method
		  REFERENCES authentication_code(code),
  auth_data	CHAR VARYING(4000)
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
		CONSTRAINT reserved_name_value_domain
		  REFERENCES value_domain_code(code),
  name		CHAR VARYING(128),
  why		CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT reserved_name_pk PRIMARY KEY (value_domain, name)
);
