/*	ou

  This table defines what Organizational Units (OUs) the institution
  is made up of.  It does not say anything about how these OUs relate
  to each other (i.e. the organizational structure); see the table
  `ou_structure' below for that.

  The names kept in this table should be in the default language for
  this installation.

 */
CREATE TABLE ou
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		NOT NULL
		DEFAULT 'o'
		CONSTRAINT ou_entity_type_chk CHECK (entity_type = 'o'),

  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_pk PRIMARY KEY,
  name		CHAR VARYING(512) NOT NULL,
  acronym	CHAR VARYING(15),
  short_name	CHAR VARYING(30),
  display_name	CHAR VARYING(80),
  sort_name	CHAR VARYING(80),
  CONSTRAINT ou_entity_id FOREIGN KEY (entity_type, ou_id)
    REFERENCES entity_id(entity_type, id)
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
