/*****
 ***** Code values related to at least two different kinds of
 ***** entities.
 *****/


/*	authoritative_system_code



*/
CREATE TABLE authoritative_system_code
(
  code		CHAR VARYING(16)
		CONSTRAINT authoritative_system_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	language_code

  Various data can appear in more than one language.  For this
  installation to accept data in a specific language, there has to be
  a language identifier ('code') for that language in this table.

  Note that it is probably a good policy (although not enforced by the
  data model) to demand registrations in at least one common language
  for all related data.  That is, even though some people would like
  to have their job title registered in Spanish, it probably isn't a
  good idea to allow this before there exists a registration in the
  language that is most commonly used for job titles.

*/
CREATE TABLE language_code
(
  code		CHAR VARYING(16)
		CONSTRAINT language_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	value_domain_code

  Various values are unique only within the "value domain" they are
  part of.  This table defines what value domains are valid in this
  installation.

  Some examples of value domains could be

   * 'unix_uid@uio.no'	- the numeric user ID value space
   * 'uname@uio.no'	- the namespace for user names
   * 'fgname@uio.no'	- the NIS filegroup namespace.

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


/*	address_code



*/
CREATE TABLE address_code
(
  code		CHAR VARYING(16)
		CONSTRAINT address_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
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


/*	contact_info_code



*/
CREATE TABLE contact_info_code
(
  code		CHAR VARYING(16)
		CONSTRAINT contact_info_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	quarantine_code

  Both persons and users can be quarantined.

*/
CREATE TABLE quarantine_code
(
  code		CHAR VARYING(16)
		CONSTRAINT quarantine_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
/* TBD: Should there be any more columns here, e.g. "duration"? */
);



/*****
 ***** Code values related to Organizational Unit (OU) entities.
 *****/


/*	ou_structure_view_code

  In some institutions the organizational structure differ among the
  various authoritative data sources.  For instance, the structure you
  get from the HR system can be different from the one used by
  Accounting.

  Most commonly such differences are rather minor -- but they still
  can be significant.

  Thus, the data model permits Organizational Units (OUs) to be
  structured in one *or* *more* ways.

  The code values for what views of the OU structure
  (e.g. 'Accounting' or 'HR') this installation allows, and what each
  of these code values signify, are kept in this table.

*/
CREATE TABLE ou_structure_view_code
(
  code		CHAR VARYING(16)
		CONSTRAINT ou_structure_view_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);



/*****
 ***** Code values related to Person entities.
 *****/


/*	gender_code



*/
CREATE TABLE gender_code
(
  code		CHAR VARYING(16)
		CONSTRAINT gender_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
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
/* TBD: Should person affiliation codes be organized in e tree
	structure, e.g. like this:

,  parent	CHAR VARYING(16)
		CONSTRAINT person_affiliation_code_parent
		  REFERENCES person_affiliation_code(code)

	This could be useful if a mapping from person(primary_source)
	to "primary affiliation" is needed for persons with several
	affiliations given from their primary_source. */
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
  CONSTRAINT person_aff_status_pk
    PRIMARY KEY (affiliation, status)
);



/*****
 ***** Code values related to User Account entities.
 *****/


/*	account_code



*/
CREATE TABLE account_code
(
  code		CHAR VARYING(16)
		CONSTRAINT account_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);
