/*** Note:
 *** The tables in code_value_tables.sql must have been created prior to
 *** the tables found here.
 ***/

/*	ou

  TBD: Are the name variants below sufficient/too many?

  TBD: Is there a need for keeping a history of OU's names?  If yes,
       should this be part of the core or put into a module?

 */
CREATE TABLE ou
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_pk PRIMARY KEY,
  name		CHAR VARYING(512) NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80)
);


/*	ou_structure

  What the organization structure (or structures, if more than one
  structure view is in use) looks like is defined by the data in this
  table.

  Note that the structure(s) are independently of the "OU identifiers"
  as they appear in the authoritative data sources.

  parent_id is NULL for root nodes.

*/
CREATE TABLE ou_structure
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_structure_ou_id REFERENCES ou(ou_id),
  structure_view
		CHAR VARYING(16)
		CONSTRAINT ou_structure_structure_view
		  REFERENCES ou_structure_view_code(code),
  parent_id	NUMERIC(12,0)
		CONSTRAINT ou_structure_parent_id REFERENCES ou(ou_id),
  CONSTRAINT ou_structure_pk PRIMARY KEY (ou_id, structure_view),
/* TBD: Should there be a `parent_structure_view', or is it okay to
        use just one `structure_view' for defining both this node and
        its parent? */
  CONSTRAINT ou_structure_parent_node
    FOREIGN KEY (parent_id, structure_view)
    REFERENCES ou_structure(ou_id, structure_view)
);


/*	ou_name_language



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
 *** Module `stedkode' -- specific to Norway.
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
/* TBD: Heter det "avdeling" eller "gruppe"? */
  avdeling	NUMERIC(2,0)
		NOT NULL,
  katalog_merke	BOOLEAN,
  CONSTRAINT stedkode_kode UNIQUE (institusjon, fakultet, institutt, avdeling)
);
