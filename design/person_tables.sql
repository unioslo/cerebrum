/*	person



*/
CREATE TABLE person
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_pk PRIMARY KEY,
/* TBD: Should we have a unique, constant ID for each person, for use
	when exporting data to other systems -- or is it sufficient to
	keep such an ID (for the persons that need it) in the
	person_external_id-table?  What happens when someone have been
	away from the institution for so long that their entry in this
	table has been deleted? */
  birth_date	DATE
		NOT NULL,
/* TBD: Kjønn kan i Norge avledes av FNR; bør kolonnen under allikevel
	finnes mhp. at tilsvarende ikke nødvendigvis er mulig i
	utlandet? */
  gender	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_gender REFERENCE gender_code(code),
  deceased	BOOLEAN,
  comment	CHAR VARYING(512)
);


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
  appear_date	DATE
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
    REFERENCES person_aff_status(affiliation, status)
);


/*	person_address



*/
CREATE TABLE person_address
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_address_person_id
		  REFERENCES person(person_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT person_address_source_system
		  REFERENCES authoritative_system_code(code),
  address_type	CHAR VARYING(16)
		CONSTRAINT person_address_address_type
		  REFERENCES address_code(code),
  aline1	CHAR VARYING(80),
  aline2	CHAR VARYING(80),
  aline3	CHAR VARYING(80),
  aline4	CHAR VARYING(80),
  p_o_box	CHAR VARYING(10),
  postal_number	CHAR VARYING(8),
  city		CHAR VARYING(128),
  country	CHAR VARYING(128),
  CONSTRAINT person_address_pk
    PRIMARY KEY (person_id, source_system, address_type)
);


/*	person_phone



*/
CREATE TABLE person_phone
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_phone_person_id
		  REFERENCES person(person_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT person_phone_source_system
		  REFERENCES authoritative_system_code(code),
  phone_type	CHAR VARYING(16)
		CONSTRAINT person_phone_phone_type
		  REFERENCES phone_code(code),
  phone_pref	NUMERIC(2,0),
  phone_number	CHAR VARYING(20)
		NOT NULL,
/* TBD: Do we need the following column?  For what purpose?  What about
        an update_date column? */
  create_date	DATE
		DEFAULT SYSDATE,
  description	CHAR VARYING(512),
  PRIMARY KEY (person_id, source_system, phone_type, phone_pref)
);


/*	person_contact_info



*/
CREATE TABLE person_contact_info
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_contact_info_person_id
		  REFERENCES person(person_id),
  source_system	CHAR VARYING(16)
		CONSTRAINT person_contact_info_source_system
		  REFERENCES authoritative_system_code(code),
  contact_type	CHAR VARYING(16)
		CONSTRAINT person_contact_info_contact_type
		  REFERENCES contact_info_code(code),
  contact_pref	NUMERIC(2,0),
  contact_value	CHAR VARYING(255)
		NOT NULL,
  description	CHAR VARYING(512),
  CONSTRAINT person_contact_info_pk
    PRIMARY KEY (person_id, source_system, contact_type, contact_pref)
);


/*	person_quarantine



*/
CREATE TABLE person_quarantine
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_quarantine_person_id
		  REFERENCES person(person_id),
  quarantine_type
		CHAR VARYING(16)
		CONSTRAINT person_quarantine_quarantine_type
		  REFERENCES quarantine_code(code),
  entered_by	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT person_quarantine_entered_by
		  REFERENCES person(person_id),
  entered_date	DATE
		NOT NULL
		DEFAULT SYSDATE,
/* TBD: Are the following two columns necessary? */
  start_date	DATE
		NOT NULL,
  end_date	DATE,
  CONSTRAINT person_quarantine_pk PRIMARY KEY (person_id, quarantine_type)
);


/***
 *** Module 'name-history' -- keep track of persons' names as they
 *** change over time.
 ***/
CREATE TABLE person_name_history
(
  person_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT person_name_history_person_id
		  REFERENCES person(person_id),
  name_variant	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_name_variant
		  REFERENCES person_name_code(code),
  source_system	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_source_system
		  REFERENCES authoritative_system_code(code),
  entry_date	DATE
		NOT NULL,
/* TBD: Should we allow NULL names (to indicate that a person have
	seized to have a value for one name_variant)? */
  name		CHAR VARYING(256)
		NOT NULL
/* TBD: Should this table have any primary key, e.g.
  CONSTRAINT person_name_history_pk PRIMARY KEY
    (person_id, name_variant, source_system, entry_date) */
);


/***
 *** Module 'SSN-change' -- keep track of change history of persons'
 *** external IDs.
 ***/
CREATE TABLE person_external_id_change
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_external_id_change_person_id
		  REFERENCES person(person_id),
  id_type	CHAR VARYING(16)
		CONSTRAINT person_external_id_change_id_type
		  REFERENCES person_external_id_code(code),
  change_date	DATE
		NOT NULL,
/* TBD: Should we mix source_system into this?
  source_system CHAR VARYING(16)
		CONSTRAINT person_external_id_change_source_system
		  REFERENCES authoritative_system_code(code), */
  old_id	CHAR VARYING(256)
		NOT NULL,
  new_id	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT person_external_id_change_pk PRIMARY KEY
    (person_id, id_type, change_date /*, source_system */)
);
