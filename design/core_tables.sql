/*	authoritative_system_code



*/
CREATE TABLE authoritative_system_code
(
  code		CHAR VARYING(16)
		CONSTRAINT authoritative_system_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	entity_type_code

  This table holds one entry per type of entity the system can collect
  data on, e.g. persons, groups and OUs.

*/
CREATE TABLE entity_type_code
(
  code		CHAR VARYING(16)
		CONSTRAINT entity_type_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);



/*	entity_info

  When an entity is to be created within an installation, it is given
  a numeric ID -- an `entity_id'.  These IDs are generated using a
  single, entity-type-independent sequence.  They are purely internal,
  i.e. they should never in any way be exported outside this system.

  This table keeps track of which entity IDs are in use, and what type
  of entity each `entity_id' is connected to.

  Garbage collection: The data model can not ensure that there will
    actually exist an entry in the `entity_type'-specific table for
    all the `entity_id's in this table.  To reduce the amount of
    `entity_info' rows with no corresponding entity we need some kind
    of garbage collector.

  TBD: Need separate `entity_type's for
	* name reservations (to be kept in the `entity_name' table)
	* ldap DNs (to allow these to members of groups)

*/
CREATE SEQUENCE entity_id_seq;
CREATE TABLE entity_info
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_info_pk PRIMARY KEY,
  entity_type	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT entity_info_entity_type
		  REFERENCES entity_type_code(code),
  CONSTRAINT entity_info_type_unique
    UNIQUE (entity_type, entity_id)
);


/*	value_domain_code

  Various values are unique only within the "value domain" they are
  part of.  This table defines what value domains are valid in this
  installation.

  Some examples of value domains could be

   * 'unix_uid@uio.no'	- the numeric user ID value space
   * 'uname@uio.no'	- the namespace for user names
   * 'fgname@uio.no'	- the NIS filegroup namespace.
   * 'unix_uid@ANY'	- all defined numeric user ID value spaces
   * 'ANY@uio.no'	- all defined value spaces @uio.no
   * 'ANY@ANY'		- all defined value spaces

  Note that this table does not try to indicate what restrictions
  there are on the various value domains (e.g. numeric values only,
  must not contain special characters like ':', or must be at most 8
  characters long); such understanding (and enforcement) of
  restrictions are left to the module code that implements access to
  any particular value space.

*/
CREATE TABLE value_domain_code
(
  code		CHAR VARYING(16)
		CONSTRAINT value_domain_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	entity_name



*/
CREATE TABLE entity_name
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_name_entity_id
		  REFERENCES entity_info(entity_id),
  value_domain	CHAR VARYING(16)
		CONSTRAINT entity_name_value_domain
		  REFERENCES value_domain_code(code),
  entity_name	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT entity_name_pk
    PRIMARY KEY (entity_id, value_domain),
  CONSTRAINT entity_name_unique_per_domain
    UNIQUE (value_domain, entity_name)
);


/*	country_code



*/
CREATE TABLE country_code
(
  code		CHAR VARYING(16)
		CONSTRAINT country_code_pk PRIMARY KEY,
  country	CHAR VARYING(64)
		NOT NULL,
  phone_prefix	CHAR VARYING(8),
  description	CHAR VARYING(512)
		NOT NULL
);


/*	address_code



*/
CREATE TABLE address_code
(
  code		CHAR VARYING(16)
		CONSTRAINT address_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	entity_address

  The column `address_text' is a (near) free-form textual
  representation of the address, with '$' used to indicate newlines.

*/
CREATE TABLE entity_address
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_address_entity_id
		  REFERENCES entity_info(entity_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT entity_address_source_system
		  REFERENCES authoritative_system_code(code),
  address_type	CHAR VARYING(16)
		CONSTRAINT entity_address_address_type
		  REFERENCES address_code(code),
  address_text	CHAR VARYING(256),
  p_o_box	CHAR VARYING(10),
  postal_number	CHAR VARYING(8),
  city		CHAR VARYING(128),
  country	CHAR VARYING(16)
		CONSTRAINT entity_address_country
		  REFERENCES country_code(code),
  CONSTRAINT entity_address_pk
    PRIMARY KEY (entity_id, source_system, address_type)
);


/*	phone_code



*/
CREATE TABLE phone_code
(
  code		CHAR VARYING(16)
		CONSTRAINT phone_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	entity_phone

  `phone_number' should contain no dashes/letters/whitespace, and
  should be fully specified.  Examples: "+4712345678" and "*12345".

  If there exists multiple `phone_number's of the same `phone_type'
  for an entity, the `phone_pref' column can be used to indicate an
  ordering between these `phone_number's; high `phone_pref' values are
  preferred.

*/
CREATE TABLE entity_phone
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_phone_entity_id
		  REFERENCES entity_info(entity_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT entity_phone_source_system
		  REFERENCES authoritative_system_code(code),
  phone_type	CHAR VARYING(16)
		CONSTRAINT entity_phone_phone_type
		  REFERENCES phone_code(code),
  phone_pref	NUMERIC(2,0)
		DEFAULT 50,
  phone_number	CHAR VARYING(20)
		NOT NULL,
  description	CHAR VARYING(512),
  CONSTRAINT entity_phone_pk
    PRIMARY KEY (entity_id, source_system, phone_type, phone_pref)
);


/*	contact_info_code



*/
CREATE TABLE contact_info_code
(
  code		CHAR VARYING(16)
		CONSTRAINT contact_info_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	entity_contact_info

  If there exists multiple `contact_value's of the same `contact_type'
  for an entity, the `contact_pref' column can be used to indicate an
  ordering between these `contact_values's; high `contact_pref' values
  are preferred.

*/
CREATE TABLE entity_contact_info
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_contact_info_entity_id
		 REFERENCES entity_info(entity_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT entity_contact_info_source_sys
		  REFERENCES authoritative_system_code(code),
  contact_type	CHAR VARYING(16)
		CONSTRAINT entity_contact_info_cont_type
		  REFERENCES contact_info_code(code),
  contact_pref	NUMERIC(2,0)
		DEFAULT 50,
  contact_value	CHAR VARYING(255)
		NOT NULL,
  description	CHAR VARYING(512),
  CONSTRAINT entity_contact_info_pk
    PRIMARY KEY (entity_id, source_system, contact_type, contact_pref)
);


/*	quarantine_code

  All kinds of entities can be quarantined.

  If 'duration' is non-NULL, it gives the quarantine's duration as a
  number of days; this is used to calculate a default value for the
  entity_quarantine(end_date) column.

*/
CREATE TABLE quarantine_code
(
  code		CHAR VARYING(16)
		CONSTRAINT quarantine_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL,
  duration	NUMERIC(4,0)
		DEFAULT NULL
);


/*	account_code

  Accounts can be either personal or non-personal.  While the data in
  table `account_type' should be sufficient to identify the type(s) of
  personal accounts, there's still a need to keep track of the various
  kinds of non-personal accounts.

  This table holds code values for these data.  Some examples of code
  values can be "system account", "program account", "group account".

*/
CREATE TABLE account_code
(
  code		CHAR VARYING(16)
		CONSTRAINT account_code_pk PRIMARY KEY,
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
CREATE TABLE account_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		DEFAULT 'u'
		NOT NULL
		CONSTRAINT account_info_entity_type_chk
		  CHECK (entity_type = 'u'),
  account_id	NUMERIC(12,0)
		CONSTRAINT account_info_pk PRIMARY KEY,
  owner_type	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT account_info_owner_type_chk
		  CHECK (owner_type IN ('p', 'g')),
  owner_id	NUMERIC(12,0)
		NOT NULL,
  np_type	CHAR VARYING(16)
		CONSTRAINT account_info_np_type
		  REFERENCES account_code(code),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT account_info_creator_id
		  REFERENCES account_info(account_id),
  expire_date	DATE
		DEFAULT NULL,
  CONSTRAINT account_info_entity_id
    FOREIGN KEY (entity_type, account_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT account_info_owner
    FOREIGN KEY (owner_type, owner_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT account_info_np_type_chk
    CHECK ((owner_type = 'p' AND np_type IS NULL) OR
	   (owner_type = 'g' AND np_type IS NOT NULL)),
/* The next constraint is needed to allow `account_type' to have a
   foreign key agains these two columns. */
  CONSTRAINT account_info_id_owner_unique
    UNIQUE (account_id, owner_id)
);


/*	entity_quarantine

  When `end_date' is NULL, the `entity_id' is quarantined
  indefinitely.

  Use the column `disable_until' to indicate that a quarantine should
  be lifted from now until the date in `disable_until'.  This is
  useful e.g. for giving users who have been quarantined for having
  too old passwords a limited time to change their password; in order
  to change their password they must use their old password, and this
  won't work when they're quarantined.

  Garbage collection: Remove rows where non-NULL `end_date' is in the
    past.

*/
CREATE TABLE entity_quarantine
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_quarantine_entity_id
		  REFERENCES entity_info(entity_id),
  quarantine_type
		CHAR VARYING(16)
		CONSTRAINT entity_quarantine_quar_type
		  REFERENCES quarantine_code(code),
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT entity_quarantine_creator_id
		  REFERENCES account_info(account_id),
  description	CHAR VARYING(512),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  start_date	DATE
		NOT NULL,
  disable_until DATE,
  end_date	DATE,
  CONSTRAINT entity_quarantine_pk
    PRIMARY KEY (entity_id, quarantine_type)
);


/*	ou_info

  This table defines what Organizational Units (OUs) the institution
  is made up of.  It does not say anything about how these OUs relate
  to each other (i.e. the organizational structure); see the table
  `ou_structure' below for that.

  The names kept in this table should be in the default language for
  this installation.

 */
CREATE TABLE ou_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		DEFAULT 'o'
		NOT NULL
		CONSTRAINT ou_info_entity_type_chk
		  CHECK (entity_type = 'o'),
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_info_pk PRIMARY KEY,
  name		CHAR VARYING(512) NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80),
  sort_name	CHAR VARYING(80),
  CONSTRAINT ou_info_entity_id
    FOREIGN KEY (entity_type, ou_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*	ou_perspective_code

  In some institutions the organizational structure differ among the
  various authoritative data sources.  For instance, the structure you
  get from the HR system can be different from the one used by
  Accounting.

  Most commonly such differences are rather minor -- but they still
  can be significant.

  Thus, the data model permits Organizational Units (OUs) to be
  structured in one *or* *more* ways.

  The code values for what perspectives of the OU structure
  (e.g. 'Accounting' or 'HR') this installation allows, and what each
  of these code values signify, are kept in this table.

*/
CREATE TABLE ou_perspective_code
(
  code		CHAR VARYING(16)
		CONSTRAINT ou_perspective_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	ou_structure

  What the organization structure (or structures, if there exists more
  than one `perspective') looks like is defined by the data in this
  table.

  Note that the structure(s) are built using nothing but the numeric,
  strictly internal OU IDs, and therefore are independent of whatever
  OU identifiers the authoritative data sources use.

  Root nodes are identified by NULL `parent_id'.

*/
CREATE TABLE ou_structure
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_structure_ou_id
		  REFERENCES ou_info(ou_id),
  perspective	CHAR VARYING(16)
		CONSTRAINT ou_structure_perspective
		  REFERENCES ou_perspective_code(code),
  parent_id	NUMERIC(12,0)
		CONSTRAINT ou_structure_parent_id
		  REFERENCES ou_info(ou_id),
  CONSTRAINT ou_structure_pk
    PRIMARY KEY (ou_id, perspective),
  CONSTRAINT ou_structure_parent_node
    FOREIGN KEY (parent_id, perspective)
    REFERENCES ou_structure(ou_id, perspective)
);


/*	language_code

  Various data can appear in more than one language.  For this
  installation to accept data in a specific language, there has to be
  a language identifier ('code') for that language in this table.

  ISO standard 639, titled "Codes for the Representation of Names of
  Languages", should do nicely for this purpose in nearly all cases.
  It is recommended that 3-letter bibliographic language names are
  used.  Please be *very* sure that you know what you're doing before
  using language codes that aren't defined in ISO 639.

  Note that it is probably a good policy (although not enforced by the
  data model) to demand registrations in at least one common language
  for all related data.  That is, even though some people would like
  to have their job title registered in e.g. Spanish, it probably
  isn't a good idea to allow this before there exists a registration
  in the language your institution most commonly uses for job titles.

*/
CREATE TABLE language_code
(
  code		CHAR VARYING(16)
		CONSTRAINT language_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	ou_name_language

  Use this table to define the names of OUs in languages other than
  the default language of this installation.

*/
CREATE TABLE ou_name_language
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_name_language_ou_id
		  REFERENCES ou_info(ou_id),
  language_code	CHAR VARYING(16)
		CONSTRAINT ou_name_language_language_code
		  REFERENCES language_code(code),
  name		CHAR VARYING(512)
		NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80),
  sort_name	CHAR VARYING(80),
  CONSTRAINT ou_name_language_pk
    PRIMARY KEY (ou_id, language_code)
);


/*	gender_code



*/
CREATE TABLE gender_code
(
  code		CHAR VARYING(16)
		CONSTRAINT gender_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	person_info

  `export_id'	Unique, constant-over-time identifier for a person.
		This is the identifier one should use when exporting
		person data outside the system.  The intention is that
		an individual should keep its `export_id' value
		forever once it has been assigned.

		TBD: Fint om man kunne garantere at denne IDen var
		unik på tvers av forskjellige Cerebrum-installasjoner;
		holder det med en felles konvensjon for hvordan IDen
		ser ut?

  TODO: Må definere API for å flytte informasjon knyttet til en
	person_id over til en annen.  Både kjernen og alle moduler må
	støtte dette.

*/
CREATE TABLE person_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		DEFAULT 'p'
		NOT NULL
		CONSTRAINT person_info_entity_type_chk
		  CHECK (entity_type = 'p'),
  person_id	NUMERIC(12,0)
		CONSTRAINT person_info_pk PRIMARY KEY,
  export_id	CHAR VARYING(16)
		DEFAULT NULL
		CONSTRAINT person_info_export_id_unique UNIQUE,
  birth_date	DATE,
  gender	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_info_gender
		  REFERENCES gender_code(code),
  deceased	CHAR(1)
		DEFAULT 'F'
		NOT NULL
		CONSTRAINT person_info_deceased_bool
		  CHECK (deceased IN ('T', 'F')),
  description	CHAR VARYING(512),
  CONSTRAINT person_info_entity_id
    FOREIGN KEY (entity_type, person_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*	person_external_id_code

  One person can have any number of "unique identifiers", though only
  one of each "identifier type".

  This table defines what types of personal unique identifiers
  ("Norwegian SSN", "Norwegian Student ID card number", etc.) that can
  be entered into this installation of the system.

*/
CREATE TABLE person_external_id_code
(
  code		CHAR VARYING(16)
		CONSTRAINT person_external_id_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	person_external_id

  There exists a lot of different ID systems for persons outside
  Cerebrum, and a person will typically have been assigned an ID in
  several of these.  To allow Cerebrum to identify a single person by
  several ID schemes, this table holds the various external person IDs
  that is known to relate to a single person.

*/
CREATE TABLE person_external_id
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_external_id_person_id
		  REFERENCES person_info(person_id),
  id_type	CHAR VARYING(16)
		CONSTRAINT person_external_id_id_type
		  REFERENCES person_external_id_code(code),
  external_id	CHAR VARYING(256),
  CONSTRAINT person_external_id_pk
    PRIMARY KEY (person_id, id_type),
  CONSTRAINT person_external_id_unique
    UNIQUE (id_type, external_id)
);


/*	person_name_code

  A person must have one or more names.  Apart from the base set of
  names in the 'person' table, these names can be split, arranged and
  formatted in any number of ways.

  This table defines what "name variants" ("First name", "Last name",
  "Prefix", "Initials", "SortName", "DisplayName", etc.) that can be
  entered into this installation of the system.

*/
CREATE TABLE person_name_code
(
  code		CHAR VARYING(16)
		CONSTRAINT person_name_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	person_name

  No name variants are considered compulsory by this data model;
  however, various export modules may deem person without a minimum
  amount of registered name data as "not exportable".

*/
CREATE TABLE person_name
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_name_person_id
		  REFERENCES person_info(person_id),
  name_variant	CHAR VARYING(16)
		CONSTRAINT person_name_name_variant
		  REFERENCES person_name_code(code),
  source_system	CHAR VARYING(16)
		CONSTRAINT person_name_source_system
		  REFERENCES authoritative_system_code(code),
  name		CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT person_name_pk
    PRIMARY KEY (person_id, name_variant, source_system)
);


/*	person_affiliation_code

  This table defines what "affiliations" this installation of the
  system can register between any person and the institution
  ("employee", "faculty", "student", "guest", etc.).

*/
CREATE TABLE person_affiliation_code
(
  code		CHAR VARYING(16)
		CONSTRAINT person_affiliation_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	person_aff_status_code

  , and what kinds of
  "status" (employee on leave, retired faculty, inactive student,
  etc.) each of these "affiliation" types can have.

*/
CREATE TABLE person_aff_status_code
(
  affiliation	CHAR VARYING(16)
		CONSTRAINT person_aff_status_affiliation
		  REFERENCES person_affiliation_code(code),
  status	CHAR VARYING(16),
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT person_aff_status_code_pk
    PRIMARY KEY (affiliation, status)
);


/*	person_affiliation

  As (personal) user accounts are connected to a person's
  affiliations, deletion of rows in this table can be cumbersome.  To
  alleviate this problem, the deleted_date column is set non-NULL in
  rows corresponding to no longer existing affiliations.

  Once an affiliation with non-NULL deleted_date no longer have any
  user accounts associated with it, that row can (and should) be
  removed.

*/
CREATE TABLE person_affiliation
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_affiliation_person_id
		  REFERENCES person_info(person_id),
  ou_id		NUMERIC(12,0)
		CONSTRAINT person_affiliation_ou_id
		  REFERENCES ou_info(ou_id),
  affiliation	CHAR VARYING(16)
		CONSTRAINT person_affiliation_affiliation
		  REFERENCES person_affiliation_code(code),
  status	CHAR VARYING(16),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  last_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  deleted_date	DATE,
  CONSTRAINT person_affiliation_pk
    PRIMARY KEY (person_id, ou_id, affiliation),
  CONSTRAINT person_affiliation_status
    FOREIGN KEY (affiliation, status)
    REFERENCES person_aff_status_code(affiliation, status)
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
  account_id	NUMERIC(12,0),
  CONSTRAINT account_type_pk
    PRIMARY KEY (person_id, ou_id, affiliation, account_id),
  CONSTRAINT account_type_affiliation
    FOREIGN KEY (person_id, ou_id, affiliation)
    REFERENCES person_affiliation(person_id, ou_id, affiliation),
  CONSTRAINT account_type_account
    FOREIGN KEY (account_id, person_id)
    REFERENCES account_info(account_id, owner_id)
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
		CONSTRAINT account_authentication_acc_id
		  REFERENCES account_info(account_id),
  method	CHAR VARYING(16)
		CONSTRAINT account_authentication_method
		  REFERENCES authentication_code(code),
  auth_data	CHAR VARYING(4000)
		NOT NULL,
  CONSTRAINT account_auth_pk
    PRIMARY KEY (account_id, method)
);


CREATE TABLE group_visibility_code
(
  code		CHAR VARYING(16)
		CONSTRAINT group_visibility_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	group_info

  gname
	Name of the group.  Must be lowercase, but can contain (some)
	non-alphabetic characters.

  visibility
	Who should the name/contents of this list be visible to?

	TBD: Should group visibility rather be implemented as part of
	     the access delegation structure?

*/
CREATE TABLE group_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		DEFAULT 'g'
		NOT NULL
		CONSTRAINT group_info_entity_type_chk
		  CHECK (entity_type = 'g'),
  group_id	NUMERIC(12,0)
		CONSTRAINT group_info_pk PRIMARY KEY,
  description	CHAR VARYING(512),
  visibility	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_info_visibility
		  REFERENCES group_visibility_code(code),
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_info_creator_id
		  REFERENCES account_info(account_id),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
/* expire_date kan brukes for å slette grupper, f.eks. ved at gruppen
   ikke lenger eksporteres etter at datoen er passert, men først
   slettes fra tabellen N måneder senere.  Det innebærer at man ikke
   får opprettet noen ny gruppe med samme navn før gruppa har vært
   borte fra eksporten i N måneder (med mindre man endrer på
   expire_date). */
  expire_date	DATE
		DEFAULT NULL,
  CONSTRAINT group_info_entity_id
    FOREIGN KEY (entity_type, group_id)
    REFERENCES entity_info(entity_type, entity_id)
);


CREATE TABLE group_membership_op_code
(
  code		CHAR VARYING(16)
		CONSTRAINT group_membership_op_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/* group_member:

  group_id
	Reference to the (super-)group this membership pertains to.

  operation

	Indicate whether this membership is a (set) 'U'nion,
	'I'ntersection or 'D'ifference.  When determining the members
	of a group, the member types are processed in this order:

	  Add all members from Union type members
	  Limit the member set using all Intersection type members
	  Reduce the member set by removing all Difference type members

 */
CREATE TABLE group_member
(
  group_id	NUMERIC(12,0)
		CONSTRAINT group_member_group_id
		  REFERENCES group_info(group_id),
  operation	CHAR VARYING(16)
		CONSTRAINT group_member_operation
		  REFERENCES group_membership_op_code(code),
  member_type	CHAR VARYING(16)
		NOT NULL,
  member_id	NUMERIC(12,0),
  CONSTRAINT group_member_pk
    PRIMARY KEY (group_id, operation, member_id),
  CONSTRAINT group_member_exists
    FOREIGN KEY (member_type, member_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT group_member_not_self
    CHECK (group_id <> member_id)
);


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


/* TBD:
 * Struktur for tildeling av ymse rettigheter til (IT-)grupper.
*/

/***********************************************************************
   Generalized group tables
 ***********************************************************************/


/*

TBD: Er de følgende to tabellene nødvendige i det hele tatt, eller bør
     de erstattes med modul-spesifikke export-tabeller m/ tilhørende
     hooks?

In what fashions/to what systems can a group be exported?

This is split into the group type and, for lack of a better name, the
target system's "owner".  This means that the same code can easily be
used to perform an export for all exports with the same gtype
(e.g. the code to expand subgroups etc. for exporting as NIS
filegroups needs only be written once).

 */

/*
CREATE TABLE group_export_type
(
  gtype		 CHAR VARYING(32),
  system_owner	 CHAR VARYING(32),
  description	 CHAR VARYING(512),
  PRIMARY KEY (gtype, system_owner) 
);
*/


/* Define how a specific group should be exported. */
/*
CREATE TABLE group_export
(
  gkey		NUMERIC(12,0)
		CONSTRAINT group_export_gkey REFERENCES group_info(group_id),
  gtype		CHAR VARYING(32),
  system_owner	CHAR VARYING(32),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  create_by	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_export_create_by
		  REFERENCES account(account_id),
  delete_date	DATE
		DEFAULT NULL,
  delete_by	NUMERIC(12,0)
		DEFAULT NULL
		CONSTRAINT group_export_delete_by
		  REFERENCES account(account_id),
  CONSTRAINT group_export_pk PRIMARY KEY (gkey, gtype, system_owner),
  CONSTRAINT group_export_gtype FOREIGN KEY (gtype, system_owner)
    REFERENCES group_export_type(gtype, system_owner)
);
*/


/* TBD: Må tenke mer på om spread skal skilles fra grupper, og
   evt. hvordan.  Skal spread være i kjernen i det hele tatt? */

/*
spread
(
  to_system
  entity_type
  user
  group
  person
  ...
  start_date
  end_date
);
*/

/* Bør man kunne override gruppenavn pr. system ved eksport?  Det vil tillate

   Internt i u2k	System X	System Y	System Z
   -------------------------------------------------------------
   A			A		foo		bar
   B			B		bar		foo
   C			C		C		A

, men *vil* vi egentlig det? */
