/*** Note:
 *** The tables in code_value_tables.sql must have been created prior to
 *** the tables found here.
 ***/

/* TBD: Dersom alle entitets-IDer har lik datatype (som
	f.eks. "NUMERIC(12,0)"), kan man benytte en og samme sekvens
	til å hente ny ID, uavhengig av hvilken type entitet IDen skal
	representere.  På denne måten vil man ende opp med at en gitt
	ID kun finnes for _en_ entitet i hele systemet.

	Er dette lurt/nødvendig/ønskelig? */


/*	ou

  This table defines what Organizational Units (OUs) the institution
  is made up of.  It does not say anything about how these OUs relate
  to each other (i.e. the organizational structure); see the table
  ou_structure below for that.

  The names kept in this table should be in the default language for
  this installation.

 */
CREATE TABLE ou
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_pk PRIMARY KEY,
  name		CHAR VARYING(512) NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80),
  sort_name	CHAR VARYING(80)
);


/*	ou_structure

  What the organization structure (or structures, if there exists more
  than one "perspective") looks like is defined by the data in this
  table.

  Note that the structure(s) are built using nothing but the numeric,
  strictly internal ID for OUs, and therefore are independent of
  whatever "OU identifiers" the authoritative data sources use.

  Root nodes are identified by NULL parent_id.

*/
CREATE TABLE ou_structure
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_structure_ou_id REFERENCES ou(ou_id),
  perspective	CHAR VARYING(16)
		CONSTRAINT ou_structure_perspective
		  REFERENCES ou_perspective_code(code),
  parent_id	NUMERIC(12,0)
		CONSTRAINT ou_structure_parent_id REFERENCES ou(ou_id),
  CONSTRAINT ou_structure_pk PRIMARY KEY (ou_id, perspective),
  CONSTRAINT ou_structure_parent_node
    FOREIGN KEY (parent_id, perspective)
    REFERENCES ou_structure(ou_id, perspective)
);


/*	ou_name_language

  Use this table to define the names of OUs in languages other than
  the default language of this installation.

*/
CREATE TABLE ou_name_language
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_name_language_ou_id
		  REFERENCES ou(ou_id),
  language_code	CHAR VARYING(16)
		CONSTRAINT ou_name_language_language_code
		  REFERENCES language_code(code),
  name		CHAR VARYING(512) NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80),
  sort_name	CHAR VARYING(80),
  CONSTRAINT ou_name_language_pk PRIMARY KEY (ou_id, language_code)
);


/*	ou_address



*/
CREATE TABLE ou_address
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_address_ou_id REFERENCES ou(ou_id),
  address_type	CHAR VARYING(16)
		CONSTRAINT ou_address_address_type
		  REFERENCES address_code(code),
  aline1	CHAR VARYING(80),
  aline2	CHAR VARYING(80),
  aline3	CHAR VARYING(80),
  aline4	CHAR VARYING(80),
  p_o_box	CHAR VARYING(10),
  postal_number	CHAR VARYING(8),
  city		CHAR VARYING(128),
  country	CHAR VARYING(128),
  CONSTRAINT ou_address_pk PRIMARY KEY (ou_id, address_type)
);


/*	ou_phone

  phone_number should contain no dashes/letters/whitespace, and should
  be fully specified.  Examples: "+4712345678" and "*12345".

*/
CREATE TABLE ou_phone
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_phone_ou_id REFERENCES ou(ou_id),
  phone_type	CHAR VARYING(16)
		CONSTRAINT ou_phone_phone_type
		  REFERENCES phone_type_code(code),
  phone_pref	NUMERIC(2,0),
  phone_number	CHAR VARYING(20)
		NOT NULL,
  description	CHAR VARYING(512),
  CONSTRAINT ou_phone_pk PRIMARY KEY (ou_id, phone_type, phone_pref)
);


/*	ou_contact_info



*/
CREATE TABLE ou_contact_info
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_contact_info_ou_id REFERENCES ou(ou_id),
  contact_type	CHAR VARYING(16)
		CONSTRAINT ou_contact_info_contact_type
		  REFERENCES contact_info_code(code),
  contact_pref	NUMERIC(2,0),
  contact_value	CHAR VARYING(255)
		NOT NULL,
  description	CHAR VARYING(512),
  CONSTRAINT ou_contact_info_pk
    PRIMARY KEY (ou_id, contact_type, contact_pref)
);



/***********************************************************************
 *** Modules related to OU. ********************************************
 ***********************************************************************/


/***

 *** Module `stedkode' -- specific to the higher education sector in
 *** Norway.

 ***/

/*	stedkode



*/
CREATE TABLE stedkode
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT stedkode_pk PRIMARY KEY
		CONSTRAINT stedkode_ou_id REFERENCES ou(ou_id),
  institusjon	NUMERIC(4,0)
		NOT NULL,
  fakultet	NUMERIC(2,0)
		NOT NULL,
  institutt	NUMERIC(2,0)
		NOT NULL,
  avdeling	NUMERIC(2,0)
		NOT NULL,
  katalog_merke	CHAR(1)
		NOT NULL
		CONSTRAINT stedkode_katalog_merke_bool
		  CHECK (katalog_merke IN ('T', 'F')),
  CONSTRAINT stedkode_kode UNIQUE (institusjon, fakultet, institutt, avdeling)
);
