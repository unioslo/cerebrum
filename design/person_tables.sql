/*	person

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
CREATE TABLE person
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		NOT NULL
		DEFAULT 'p'
		CONSTRAINT person_entity_type_chk CHECK (entity_type = 'p'),

  person_id	NUMERIC(12,0)
		CONSTRAINT person_pk PRIMARY KEY,
  export_id	CHAR VARYING(16)
		DEFAULT NULL
		CONSTRAINT person_export_id_unique UNIQUE,
  birth_date	DATE
		NOT NULL,
  gender	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_gender REFERENCES gender_code(code),
  deceased	CHAR(1)
		NOT NULL
		CONSTRAINT person_deceased_bool
		  CHECK (deceased IN ('T', 'F')),
  comment	CHAR VARYING(512),
  CONSTRAINT person_entity_id FOREIGN KEY (entity_type, person_id)
    REFERENCES entity_id(entity_type, id)
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
		  REFERENCES person(person_id),
  id_type	CHAR VARYING(16)
		CONSTRAINT person_external_id_id_type
		  REFERENCES person_external_id_code(code),
  external_id	CHAR VARYING(256),
  CONSTRAINT person_external_id_pk PRIMARY KEY (person_id, id_type),
  CONSTRAINT person_external_id_unique UNIQUE (id_type, external_id)
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
		  REFERENCES person(person_id),
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
		  REFERENCES person(person_id),
  ou_id		NUMERIC(12,0)
		CONSTRAINT person_affiliation_ou_id
		  REFERENCES ou(ou_id),
  affiliation	CHAR VARYING(16)
		CONSTRAINT person_affiliation_affiliation
		  REFERENCES person_affiliation_code(code),
  status	CHAR VARYING(16),
  create_date	DATE
		NOT NULL
		DEFAULT SYSDATE,
  last_date	DATE
		NOT NULL
		DEFAULT SYSDATE,
  deleted_date	DATE,
  CONSTRAINT person_affiliation_pk
    PRIMARY KEY (person_id, ou_id, affiliation),
  CONSTRAINT person_affiliation_status
    FOREIGN KEY (affiliation, status)
    REFERENCES person_aff_status_code(affiliation, status)
);
