/*
 * Copyright 2002, 2003 University of Oslo, Norway
 * 
 * This file is part of Cerebrum.
 * 
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 *
 */


/* Define role hierarchy used for granting access to various database
   objects.

   Currently, this is only done when running on an Oracle database. */

category:code/Oracle;
CREATE ROLE read_code NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_code NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code TO change_code;

category:code/Oracle;
CREATE ROLE read_entity NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_entity NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_entity TO change_entity;
category:code/Oracle;
CREATE ROLE read_ou NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_ou NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_ou TO change_ou;
category:code/Oracle;
CREATE ROLE read_person NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_person NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_person TO change_person;
category:code/Oracle;
CREATE ROLE read_account NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_account NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_account TO change_account;
category:code/Oracle;
CREATE ROLE read_group NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_group NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_group TO change_group;

category:code/Oracle;
CREATE ROLE read_core_table NOT IDENTIFIED;
category:code/Oracle;
GRANT read_code, read_entity, read_ou, read_person, read_account,
      read_group
  TO read_core_table;

category:code/Oracle;
CREATE ROLE change_core_table NOT IDENTIFIED;
category:code/Oracle;
GRANT change_code, change_entity, change_ou, change_person,
      change_account, change_group
  TO change_core_table;


category:code;
CREATE SEQUENCE code_seq;
-- No Oracle GRANT is necessary for this sequence, as all code values
-- should be defined by the table owner.


/*	authoritative_system_code



*/
category:code;
CREATE TABLE authoritative_system_code
(
  code		NUMERIC(6,0)
		CONSTRAINT authoritative_system_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT authoritative_system_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON authoritative_system_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON authoritative_system_code TO change_code;


/*	entity_type_code

  This table holds one entry per type of entity the system can collect
  data on, e.g. persons, groups and OUs.

  Note about the actual values signifying entity types:

    Entity types are coded as numbers.  The actual numbers signifying
    the specific entity types are not part of the core setup, hence
    the number used for e.g. a 'person' entity type might vary from
    installation to installation.
 
    This complicates the (entity_type, entity_id) FK constraints from
    e.g. person_info to entity_info, as one needs to know the actual
    code value the installation uses in order to write the CHECK
    constraint (and the DEFAULT value).
 
    The upshot of all this is that code value tables have to be
    created and code values have to be inserted before any data tables
    having code-value-specific constraints can be created.  Data value
    table definition will then use '[:get_constant]' constructs for
    looking up the sequence-generated numerical code values.

*/
category:code;
CREATE TABLE entity_type_code
(
  code		NUMERIC(6,0)
		CONSTRAINT entity_type_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT entity_type_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON entity_type_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_type_code TO change_code;



category:main;
CREATE SEQUENCE entity_id_seq;
category:main/Oracle;
GRANT SELECT ON entity_id_seq TO change_entity;


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
category:main;
CREATE TABLE entity_info
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_info_pk PRIMARY KEY,
  entity_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT entity_info_entity_type
		  REFERENCES entity_type_code(code),
  CONSTRAINT entity_info_type_unique
    UNIQUE (entity_type, entity_id)
);
category:main/Oracle;
GRANT SELECT ON entity_info TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_info TO change_entity;


/*	spread_code

  `code` is the numeric code for a spread type.  New rows should take
      the value of this column the `code_seq` sequence. The primary
      intended use for this is in foreign key constraints.

  `code_str` is a short, textual description of a spread type,
      suitable for terse user presentation.

  `entity_type` denotes the entity type that it is possible to give
      spread of type `code` to.  Note that this implies that any
      single spread type can only be given to a single type of
      entities, so you'll need several spread `code`s for
      e.g. exporting to a NIS domain that can handle e.g. both
      `account` and `group` entities.

  `description` is a longer textual description of a spread type.

  Some possible uses:
  code  code_str        entity_type  description
  1     'NIS_user@uio'  <account>    'User in NIS domain "uio"'
  42    'NIS_fg@uio'    <group>      'File group in NIS domain "uio"'
  43    'NIS_ng@uio'    <group>      'Net group in NIS domain "uio"'
  45    'LDAP_person'   <person>     'Person included in LDAP directory'
  47    'LDAP_OU'       <ou>         'OU included in LDAP directory'

*/
category:code;
CREATE TABLE spread_code
(
  code		NUMERIC(6,0)
		CONSTRAINT spread_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT spread_codestr_u UNIQUE,
  entity_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT spread_code_entity_type
		  REFERENCES entity_type_code(code),
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT spread_code_type_unique UNIQUE (code, entity_type)
);
category:code/Oracle;
GRANT SELECT ON spread_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON spread_code TO change_code;


/*	entity_spread

  `entity_id` identifies the entity which is given spread type
      `spread`.

  `entity_type` is needed to make sure that `entity_id` is of the
      proper entity type for receiving spread type `spread`.

  `spread` denotes the type of spread that `entity_id` is to receive;
      see table `spread_code` for how spread types are defined.

*/
category:main;
CREATE TABLE entity_spread
(
  entity_id	NUMERIC(12,0),
  entity_type	NUMERIC(6,0),
  spread	NUMERIC(6,0),
  CONSTRAINT entity_spread_pk PRIMARY KEY (entity_id, spread),
  CONSTRAINT entity_spread_entity_id FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT entity_spread_spread FOREIGN KEY (spread, entity_type)
    REFERENCES spread_code(code, entity_type)
);
category:main/Oracle;
GRANT SELECT ON entity_spread TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_spread TO change_entity;


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
category:code;
CREATE TABLE value_domain_code
(
  code		NUMERIC(6,0)
		CONSTRAINT value_domain_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT value_domain_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON value_domain_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON value_domain_code TO change_code;


/*	entity_name



*/
category:main;
CREATE TABLE entity_name
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_name_entity_id
		  REFERENCES entity_info(entity_id),
  value_domain	NUMERIC(6,0)
		CONSTRAINT entity_name_value_domain
		  REFERENCES value_domain_code(code),
  entity_name	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT entity_name_pk
    PRIMARY KEY (entity_id, value_domain),
  CONSTRAINT entity_name_unique_per_domain
    UNIQUE (value_domain, entity_name)
);
category:main/Oracle;
GRANT SELECT ON entity_name TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_name TO change_entity;


/*	country_code



*/
category:code;
CREATE TABLE country_code
(
  code		NUMERIC(6,0)
		CONSTRAINT country_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT country_codestr_u UNIQUE,
  country	CHAR VARYING(64)
		NOT NULL,
  phone_prefix	CHAR VARYING(8),
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON country_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON country_code TO change_code;


/*	address_code



*/
category:code;
CREATE TABLE address_code
(
  code		NUMERIC(6,0)
		CONSTRAINT address_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT address_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON address_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON address_code TO change_code;


/*	entity_address

  The column `address_text' is a (near) free-form textual
  representation of the address, with '$' used to indicate newlines.

*/
category:main;
CREATE TABLE entity_address
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_address_entity_id
		  REFERENCES entity_info(entity_id),
  source_system	NUMERIC(6,0)
		CONSTRAINT entity_address_source_system
		  REFERENCES authoritative_system_code(code),
  address_type	NUMERIC(6,0)
		CONSTRAINT entity_address_address_type
		  REFERENCES address_code(code),
  address_text	CHAR VARYING(256),
  p_o_box	CHAR VARYING(10),
  postal_number	CHAR VARYING(8),
  city		CHAR VARYING(128),
  country	NUMERIC(6,0)
		CONSTRAINT entity_address_country
		  REFERENCES country_code(code),
  CONSTRAINT entity_address_pk
    PRIMARY KEY (entity_id, source_system, address_type)
);
category:main/Oracle;
GRANT SELECT ON entity_address TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_address TO change_entity;


/*	contact_info_code



*/
category:code;
CREATE TABLE contact_info_code
(
  code		NUMERIC(6,0)
		CONSTRAINT contact_info_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT contact_info_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON contact_info_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON contact_info_code TO change_code;


/*	entity_contact_info

  If there exists multiple `contact_value's of the same `contact_type'
  for an entity, the `contact_pref' column can be used to indicate an
  ordering between these `contact_values's; high `contact_pref' values
  are preferred.

*/
category:main;
CREATE TABLE entity_contact_info
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_contact_info_entity_id
		 REFERENCES entity_info(entity_id),
  source_system	NUMERIC(6,0)
		CONSTRAINT entity_contact_info_source_sys
		  REFERENCES authoritative_system_code(code),
  contact_type	NUMERIC(6,0)
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
category:main/Oracle;
GRANT SELECT ON entity_contact_info TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_contact_info TO change_entity;


/*	quarantine_code

  All kinds of entities can be quarantined.

  If 'duration' is non-NULL, it gives the quarantine's duration as a
  number of days; this is used to calculate a default value for the
  entity_quarantine(end_date) column.

*/
category:code;
CREATE TABLE quarantine_code
(
  code		NUMERIC(6,0)
		CONSTRAINT quarantine_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT quarantine_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL,
  duration	NUMERIC(4,0)
		DEFAULT NULL
);
category:code/Oracle;
GRANT SELECT ON quarantine_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON quarantine_code TO change_code;


/*	host_info

   name is the DNS name that one must log into to get access to the
   machines disks.

*/
category:main;
CREATE TABLE host_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_host]
		NOT NULL
		CONSTRAINT host_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_host]),
  host_id	NUMERIC(6,0) 
                CONSTRAINT host_info_pk PRIMARY KEY,
  name		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT host_info_name_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT host_info_entity_id 
    FOREIGN KEY (entity_type, host_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*	disk_info

  path is the name of the directory that users are placed in and that
       will ocour in the NIS map, excluding trailing slash.  
*/
category:main;
CREATE TABLE disk_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_disk]
		NOT NULL
		CONSTRAINT disk_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_disk]),
  disk_id	NUMERIC(6,0)
                CONSTRAINT disk_info_pk PRIMARY KEY,
  host_id	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT disk_info_host_id
		  REFERENCES host_info(host_id),
  path		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT disk_info_path_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT disk_info_entity_id 
    FOREIGN KEY (entity_type, disk_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*	account_code

  Accounts can be either personal or non-personal.  While the data in
  table `account_type' should be sufficient to identify the type(s) of
  personal accounts, there's still a need to keep track of the various
  kinds of non-personal accounts.

  This table holds code values for these data.  Some examples of code
  values can be "system account", "program account", "group account".

*/
category:code;
CREATE TABLE account_code
(
  code		NUMERIC(6,0)
		CONSTRAINT account_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT account_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON account_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON account_code TO change_code;


/*	account_info

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

 np_type: "Non-personal" account type for accounts.  This is required
          to be set for non-personal accounts, and *can* be set for
          personal accounts as well (e.g. to indicate that a personal
          account is a "test account").

 */
category:main;
CREATE TABLE account_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_account]
		NOT NULL
		CONSTRAINT account_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_account]),
  account_id	NUMERIC(12,0)
		CONSTRAINT account_info_pk PRIMARY KEY,
  owner_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT account_info_owner_type_chk
		  CHECK (owner_type IN ([:get_constant name=entity_person],
					[:get_constant name=entity_group])),
  owner_id	NUMERIC(12,0)
		NOT NULL,
  np_type	NUMERIC(6,0)
		CONSTRAINT account_info_np_type
		  REFERENCES account_code(code),
  create_date	DATE
		DEFAULT [:now]
		NOT NULL,
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT account_info_creator_id
		  REFERENCES account_info(account_id),
  home		CHAR VARYING(512) NULL,
  disk_id       NUMERIC(6,0) NULL
                CONSTRAINT account_info_disk_id REFERENCES disk_info(disk_id),
  expire_date	DATE
		DEFAULT NULL,
  CONSTRAINT account_info_entity_id
    FOREIGN KEY (entity_type, account_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT account_info_owner
    FOREIGN KEY (owner_type, owner_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT account_info_np_type_chk
    CHECK ((owner_type = [:get_constant name=entity_person]) OR
	   (owner_type = [:get_constant name=entity_group] AND
	    np_type IS NOT NULL)),
/* The next constraint is needed to allow `account_type' to have a
   foreign key agains these two columns. */
  CONSTRAINT account_info_id_owner_unique
    UNIQUE (account_id, owner_id)
);
category:main/Oracle;
GRANT SELECT ON account_info TO read_account;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON account_info TO change_account;


/*	entity_quarantine

  When `end_date' is NULL, the `entity_id' is quarantined
  indefinitely.  Code setting `end_date' might use the `duration'
  column in quarantine_code as a default number of days from
  start_date.

  Use the column `disable_until' to indicate that a quarantine should
  be lifted from now until the date in `disable_until'.  This is
  useful e.g. for giving users who have been quarantined for having
  too old passwords a limited time to change their password; in order
  to change their password they must use their old password, and this
  won't work when they're quarantined.

  Garbage collection: Remove rows where non-NULL `end_date' is in the
    past.

*/
category:main;
CREATE TABLE entity_quarantine
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT entity_quarantine_entity_id
		  REFERENCES entity_info(entity_id),
  quarantine_type
		NUMERIC(6,0)
		CONSTRAINT entity_quarantine_quar_type
		  REFERENCES quarantine_code(code),
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT entity_quarantine_creator_id
		  REFERENCES account_info(account_id),
  description	CHAR VARYING(512),
  create_date	DATE
		DEFAULT [:now]
		NOT NULL,
  start_date	DATE
		NOT NULL,
  disable_until DATE,
  end_date	DATE,
  CONSTRAINT entity_quarantine_pk
    PRIMARY KEY (entity_id, quarantine_type)
);
category:main/Oracle;
GRANT SELECT ON entity_quarantine TO read_entity;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON entity_quarantine TO change_entity;


/*	ou_info

  This table defines what Organizational Units (OUs) the institution
  is made up of.  It does not say anything about how these OUs relate
  to each other (i.e. the organizational structure); see the table
  `ou_structure' below for that.

  The names kept in this table should be in the default language for
  this installation.

 */
category:main;
CREATE TABLE ou_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_ou]
		NOT NULL
		CONSTRAINT ou_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_ou]),
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
category:main/Oracle;
GRANT SELECT ON ou_info TO read_ou;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON ou_info to change_ou;


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
category:code;
CREATE TABLE ou_perspective_code
(
  code		NUMERIC(6,0)
		CONSTRAINT ou_perspective_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT ou_perspective_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON ou_perspective_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON ou_perspective_code TO change_code;


/*	ou_structure

  What the organization structure (or structures, if there exists more
  than one `perspective') looks like is defined by the data in this
  table.

  Note that the structure(s) are built using nothing but the numeric,
  strictly internal OU IDs, and therefore are independent of whatever
  OU identifiers the authoritative data sources use.

  Root nodes are identified by NULL `parent_id'.

*/
category:main;
CREATE TABLE ou_structure
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_structure_ou_id
		  REFERENCES ou_info(ou_id),
  perspective	NUMERIC(6,0)
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
category:main/Oracle;
GRANT SELECT ON ou_structure TO read_ou;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON ou_structure to change_ou;


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
category:code;
CREATE TABLE language_code
(
  code		NUMERIC(6,0)
		CONSTRAINT language_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT language_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON language_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON language_code TO change_code;


/*	ou_name_language

  Use this table to define the names of OUs in languages other than
  the default language of this installation.

*/
category:main;
CREATE TABLE ou_name_language
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT ou_name_language_ou_id
		  REFERENCES ou_info(ou_id),
  language_code	NUMERIC(6,0)
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
category:main/Oracle;
GRANT SELECT ON ou_name_language TO read_ou;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON ou_name_language to change_ou;


/*	gender_code



*/
category:code;
CREATE TABLE gender_code
(
  code		NUMERIC(6,0)
		CONSTRAINT gender_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT gender_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON gender_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON gender_code TO change_code;


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
category:main;
CREATE TABLE person_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_person]
		NOT NULL
		CONSTRAINT person_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_person]),
  person_id	NUMERIC(12,0)
		CONSTRAINT person_info_pk PRIMARY KEY,
  export_id	CHAR VARYING(16)
		DEFAULT NULL
		CONSTRAINT person_info_export_id_unique UNIQUE,
  birth_date	DATE,
  gender	NUMERIC(6,0)
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
category:main/Oracle;
GRANT SELECT ON person_info TO read_person;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_info TO change_person;


/*	person_external_id_code

  One person can have any number of "unique identifiers", though only
  one of each "identifier type".

  This table defines what types of personal unique identifiers
  ("Norwegian SSN", "Norwegian Student ID card number", etc.) that can
  be entered into this installation of the system.

*/
category:code;
CREATE TABLE person_external_id_code
(
  code		NUMERIC(6,0)
		CONSTRAINT person_external_id_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_external_id_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON person_external_id_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_external_id_code TO change_code;


/*	person_external_id

  There exists a lot of different ID systems for persons outside
  Cerebrum, and a person will typically have been assigned an ID in
  several of these.  To allow Cerebrum to identify a single person by
  several ID schemes, this table holds the various external person IDs
  that is known to relate to a single person.

*/
category:main;
CREATE TABLE person_external_id
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_external_id_person_id
		  REFERENCES person_info(person_id),
  id_type	NUMERIC(6,0)
		CONSTRAINT person_external_id_id_type
		  REFERENCES person_external_id_code(code),
  source_system	NUMERIC(6,0)
		CONSTRAINT person_external_id_source_sys
		  REFERENCES authoritative_system_code(code),
  external_id	CHAR VARYING(256),
  CONSTRAINT person_external_id_pk
    PRIMARY KEY (person_id, id_type, source_system),
  CONSTRAINT person_external_id_unique
    UNIQUE (id_type, source_system, external_id)
);
category:main/Oracle;
GRANT SELECT ON person_external_id TO read_person;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_external_id TO change_person;


/*	person_name_code

  A person must have one or more names.  Apart from the base set of
  names in the 'person' table, these names can be split, arranged and
  formatted in any number of ways.

  This table defines what "name variants" ("First name", "Last name",
  "Prefix", "Initials", "SortName", "DisplayName", etc.) that can be
  entered into this installation of the system.

*/
category:code;
CREATE TABLE person_name_code
(
  code		NUMERIC(6,0)
		CONSTRAINT person_name_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON person_name_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_name_code TO change_code;


/*	person_name

  No name variants are considered compulsory by this data model;
  however, various export modules may deem person without a minimum
  amount of registered name data as "not exportable".

*/
category:main;
CREATE TABLE person_name
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_name_person_id
		  REFERENCES person_info(person_id),
  name_variant	NUMERIC(6,0)
		CONSTRAINT person_name_name_variant
		  REFERENCES person_name_code(code),
  source_system	NUMERIC(6,0)
		CONSTRAINT person_name_source_system
		  REFERENCES authoritative_system_code(code),
  name		CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT person_name_pk
    PRIMARY KEY (person_id, name_variant, source_system)
);
category:main/Oracle;
GRANT SELECT ON person_name TO read_person;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_name TO change_person;


/*	person_affiliation_code

  This table defines what "affiliations" this installation of the
  system can register between any person and the institution
  ("employee", "faculty", "student", "guest", etc.).

*/
category:code;
CREATE TABLE person_affiliation_code
(
  code		NUMERIC(6,0)
		CONSTRAINT person_affiliation_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_affiliation_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON person_affiliation_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_affiliation_code TO change_code;


/*	person_affiliation

  This table is a "source_system"-indifferent/slightly simplified copy
  of the data in person_affiliation_source.  Even though all the data
  in this table is really redundant, it's needed to allow
  ("source_system"-indifferent) foreign keys from account_type to
  persons' affiliations -- as foreign keys must refer set of parent
  table columns that are guaranteed to be unique.

  As (personal) user accounts are connected to a person's
  affiliations, deletion of rows in this table can be cumbersome.  To
  alleviate this problem, the deleted_date column in
  person_affiliation_source is set non-NULL in rows corresponding to
  no longer existing affiliations.

  Once an affiliation with non-NULL deleted_date no longer have any
  user accounts associated with it, that row can (and should) be
  removed -- from both person_affiliation_source and
  person_affiliation.

*/
category:main;
CREATE TABLE person_affiliation
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_affiliation_person_id
		  REFERENCES person_info(person_id),
  ou_id		NUMERIC(12,0)
		CONSTRAINT person_affiliation_ou_id
		  REFERENCES ou_info(ou_id),
  affiliation	NUMERIC(6,0)
		CONSTRAINT person_affiliation_affiliation
		  REFERENCES person_affiliation_code(code),
  CONSTRAINT person_affiliation_pk
    PRIMARY KEY (person_id, ou_id, affiliation)
);
category:main/Oracle;
GRANT SELECT ON person_affiliation TO read_person;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_affiliation TO change_person;


/*	person_aff_status_code

  This table defines the valid ('person_affiliation_code.code',
  'status') tuples for this installation.  Any 'affiliation' code (as
  defined in person_affiliation_code) must have at least one valid
  'status' to be usable.

  Persons can be associated with multiple (affiliation, status)
  combinations (e.g. both employee and student), but cannot have more
  than one 'status' per 'affiliation'; see table
  person_affiliation_source.

  As an example, here are some believed-to-be-common entries:
    affiliation  status  status_str  description
    <employee>   57      'active'    'Employee not on leave'
    <employee>   58      'on_leave'  'Employee currently on leave'
    <faculty>    60      'active'    'Active faculty'
    <faculty>    61      'retired'   'Retired faculty'
    <student>    65      'active'    'Currently active student'
    <student>    66      'inactive'  'Student not currently active'

*/
category:code;
CREATE TABLE person_aff_status_code
(
  affiliation	NUMERIC(6,0)
		CONSTRAINT person_aff_status_affiliation
		  REFERENCES person_affiliation_code(code),
  status	NUMERIC(6,0),
  status_str	CHAR VARYING(16)
		NOT NULL,
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT person_aff_status_code_pk
    PRIMARY KEY (affiliation, status),
  CONSTRAINT person_aff_status_codestr_u
    UNIQUE (affiliation, status_str)
);
category:code/Oracle;
GRANT SELECT ON person_aff_status_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_aff_status_code TO change_code;


/*	person_affiliation_source

  last_date: The most recent date this affiliation was seen in the
        data from source_system.

  deleted_date: When an affiliation does not appear in the data from
        source_system, this column is set to the current date.  See
        description of table person_affiliation for why such
        affiliations can't be removed right away.

*/
category:main;
CREATE TABLE person_affiliation_source
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_aff_src_person_id
		  REFERENCES person_info(person_id),
  ou_id		NUMERIC(12,0)
		CONSTRAINT person_aff_src_ou_id
		  REFERENCES ou_info(ou_id),
  affiliation	NUMERIC(6,0)
		CONSTRAINT person_aff_src_affiliation
		  REFERENCES person_affiliation_code(code),
  source_system	NUMERIC(6,0)
		CONSTRAINT person_aff_src_source_sys
		  REFERENCES authoritative_system_code(code),
  status	NUMERIC(6,0),
  create_date	DATE
		DEFAULT [:now]
		NOT NULL,
  last_date	DATE
		DEFAULT [:now]
		NOT NULL,
  deleted_date	DATE
		DEFAULT NULL,
  CONSTRAINT person_aff_src_pk
    PRIMARY KEY (person_id, ou_id, affiliation, source_system),
  CONSTRAINT person_aff_src_exists
    FOREIGN KEY (person_id, ou_id, affiliation)
    REFERENCES person_affiliation(person_id, ou_id, affiliation),
  CONSTRAINT person_aff_src_status
    FOREIGN KEY (affiliation, status)
    REFERENCES person_aff_status_code(affiliation, status)
);
category:main/Oracle;
GRANT SELECT ON person_affiliation_source TO read_person;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON person_affiliation_source TO change_person;


/*	account_type

  Indicate which of the owner's affiliations a specific `account' is
  meant to cover.

  Keeping foreign keys involving person_id against both
  `person_affiliation' and `account' (which in turn has a foreign key
  against `person') ensures that all affiliations connected to a
  specific (personal) user_account belongs to the same person.

*/
category:main;
CREATE TABLE account_type
(
  person_id	NUMERIC(12,0),
  ou_id		NUMERIC(12,0),
  affiliation	NUMERIC(6,0),
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
category:main/Oracle;
GRANT SELECT ON account_type TO read_account;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON account_type TO change_account;


/*	authentication_code



*/
category:code;
CREATE TABLE authentication_code
(
  code		NUMERIC(6,0)
		CONSTRAINT authentication_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT authentication_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON authentication_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON authentication_code TO change_code;


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
category:main;
CREATE TABLE account_authentication
(
  account_id	NUMERIC(12,0)
		CONSTRAINT account_authentication_acc_id
		  REFERENCES account_info(account_id),
  method	NUMERIC(6,0)
		CONSTRAINT account_authentication_method
		  REFERENCES authentication_code(code),
  auth_data	CHAR VARYING(4000)
		NOT NULL,
  CONSTRAINT account_auth_pk
    PRIMARY KEY (account_id, method)
);
category:main/Oracle;
GRANT SELECT ON account_authentication TO read_account;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON account_authentication
  TO change_account;


/*	group_visibility_code



*/
category:code;
CREATE TABLE group_visibility_code
(
  code		NUMERIC(6,0)
		CONSTRAINT group_visibility_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_visibility_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON group_visibility_code TO read_code;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON group_visibility_code
  TO change_code;


/*	group_info

  gname
	Name of the group.  Must be lowercase, but can contain (some)
	non-alphabetic characters.

  visibility
	Who should the name/contents of this list be visible to?

	TBD: Should group visibility rather be implemented as part of
	     the access delegation structure?

*/
category:main;
CREATE TABLE group_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_group]
		NOT NULL
		CONSTRAINT group_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_group]),
  group_id	NUMERIC(12,0)
		CONSTRAINT group_info_pk PRIMARY KEY,
  description	CHAR VARYING(512),
  visibility	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT group_info_visibility
		  REFERENCES group_visibility_code(code),
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_info_creator_id
		  REFERENCES account_info(account_id),
  create_date	DATE
		DEFAULT [:now]
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
category:main/Oracle;
GRANT SELECT ON group_info TO read_group;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON group_info TO change_group;


/*	group_membership_op_code



*/
category:code;
CREATE TABLE group_membership_op_code
(
  code		NUMERIC(6,0)
		CONSTRAINT group_membership_op_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_membership_op_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:main/Oracle;
GRANT SELECT ON group_membership_op_code TO read_code;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON group_membership_op_code
  TO change_code;


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
category:main;
CREATE TABLE group_member
(
  group_id	NUMERIC(12,0)
		CONSTRAINT group_member_group_id
		  REFERENCES group_info(group_id),
  operation	NUMERIC(6,0)
		CONSTRAINT group_member_operation
		  REFERENCES group_membership_op_code(code),
  member_type	NUMERIC(6,0)
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
category:main/Oracle;
GRANT SELECT ON group_member TO read_group;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON group_member TO change_group;


-- Grant roles to users
category:main/Oracle;
GRANT change_core_table TO cerebrum_user;


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


category:drop;
DROP TABLE group_member;
category:drop;
DROP TABLE group_membership_op_code;
category:drop;
DROP TABLE group_info;
category:drop;
DROP TABLE group_visibility_code;
category:drop;
DROP TABLE account_authentication;
category:drop;
DROP TABLE authentication_code;
category:drop;
DROP TABLE account_type;
category:drop;
DROP TABLE person_affiliation_source;
category:drop;
DROP TABLE person_aff_status_code;
category:drop;
DROP TABLE person_affiliation;
category:drop;
DROP TABLE person_affiliation_code;
category:drop;
DROP TABLE person_name;
category:drop;
DROP TABLE person_name_code;
category:drop;
DROP TABLE person_external_id;
category:drop;
DROP TABLE person_external_id_code;
category:drop;
DROP TABLE person_info;
category:drop;
DROP TABLE gender_code;
category:drop;
DROP TABLE ou_name_language;
category:drop;
DROP TABLE language_code;
category:drop;
DROP TABLE ou_structure;
category:drop;
DROP TABLE ou_perspective_code;
category:drop;
DROP TABLE ou_info;
category:drop;
DROP TABLE entity_quarantine;
category:drop;
DROP TABLE account_info;
category:drop;
DROP TABLE account_code;
category:drop;
DROP TABLE disk_info;
category:drop;
DROP TABLE host_info;
category:drop;
DROP TABLE quarantine_code;
category:drop;
DROP TABLE entity_contact_info;
category:drop;
DROP TABLE contact_info_code;
category:drop;
DROP TABLE entity_address;
category:drop;
DROP TABLE address_code;
category:drop;
DROP TABLE country_code;
category:drop;
DROP TABLE entity_name;
category:drop;
DROP TABLE value_domain_code;
category:drop;
DROP TABLE entity_spread;
category:drop;
DROP TABLE spread_code;
category:drop;
DROP TABLE entity_info;
category:drop;
DROP SEQUENCE entity_id_seq;
category:drop;
DROP TABLE entity_type_code;
category:drop;
DROP TABLE authoritative_system_code;
category:drop;
DROP SEQUENCE code_seq;

category:drop/Oracle;
DROP ROLE change_core_table;
category:drop/Oracle;
DROP ROLE read_core_table;
category:drop/Oracle;
DROP ROLE change_group;
category:drop/Oracle;
DROP ROLE read_group;
category:drop/Oracle;
DROP ROLE change_account;
category:drop/Oracle;
DROP ROLE read_account;
category:drop/Oracle;
DROP ROLE change_person;
category:drop/Oracle;
DROP ROLE read_person;
category:drop/Oracle;
DROP ROLE change_ou;
category:drop/Oracle;
DROP ROLE read_ou;
category:drop/Oracle;
DROP ROLE change_entity;
category:drop/Oracle;
DROP ROLE read_entity;
category:drop/Oracle;
DROP ROLE change_code;
category:drop/Oracle;
DROP ROLE read_code;
