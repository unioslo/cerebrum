/*
 * Copyright 2003 University of Oslo, Norway
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


category:code/Oracle;
CREATE ROLE read_mod_email NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_email NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_email TO change_mod_email;

category:code/Oracle;
GRANT read_mod_email TO read_core_table;
category:code/Oracle;
GRANT change_mod_email TO change_core_table;


/*

  TBD: Should the email-related stuff become entities?  If yes,
       should any of the "names" in email addresses (i.e. domain names
       and local parts) be moved out of email-specific tables, and
       rather use the generic table entity_name (with appropriate
       value_domains)?

*/


category:code;
CREATE SEQUENCE email_id_seq;
category:code/Oracle;
GRANT SELECT ON email_id_seq TO read_mod_email;


/*	email_target_code

  Define valid target types, e.g. 'user', 'pipe', 'file', 'Mailman'.

*/
category:code;
CREATE TABLE email_target_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_target_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_target_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_target_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_target_code TO read_mod_email;


/*	email_target

  Define all targets this email system should know about.

  For (at least) `pipe` and `file` targets it is necessary to specify
  which user the delivery should be done as; use column 'entity_id' to
  hold this information on these 'target_type's.

  TBD: Do we need to specify both the `user` and the `group` a
       delivery should be run under?  If yes, how should we model
       that?

  TBD: How should "user target -> specific IMAP server" info be
       modelled?

*/
category:main;
CREATE TABLE email_target
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_target_pk PRIMARY KEY,
  target_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_target_target_type
		  REFERENCES email_target_code(code),
  entity_type	NUMERIC(6,0),
  entity_id	NUMERIC(12,0),
  alias_value	CHAR VARYING(512),
  CONSTRAINT email_target_entity FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT email_target_entity_type
    CHECK (entity_type IS NULL OR
	   entity_type IN ([:get_constant name=entity_account],
			   [:get_constant name=entity_group])),
  CONSTRAINT email_target_unique UNIQUE (entity_id, alias_value)
);
category:main/Oracle;
GRANT SELECT ON email_target TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_target TO read_mod_email;


/*	email_domain



*/
category:main;
CREATE TABLE email_domain
(
  domain_id	NUMERIC(12,0)
		CONSTRAINT email_domain_pk PRIMARY KEY,
  domain	CHAR VARYING(128)
		NOT NULL
		CONSTRAINT email_domain_domain_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:main/Oracle;
GRANT SELECT ON email_domain TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_domain TO read_mod_email;


/*	email_domain_cat_code

  Define valid maildomain category types.  Some examples:

    code_str      description

    'no_export'   'Addresses in these domains can be defined, but are
                   not exported to the mail system.  This is useful
                   for pre-defining addresses prior to taking over a
                   new maildomain.'
    'fullname'    'Primary user addresses in these domains will be
                   based on the owner's full name, and not just the
                   user's username.'
    'uname'       'Primary user addresses in these domains will be on
                   the format username@domain.'

*/
category:code;
CREATE TABLE email_domain_cat_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_domain_cat_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_domain_cat_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_domain_cat_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_domain_cat_code TO read_mod_email;


/*	email_domain_category



*/
category:main;
CREATE TABLE email_domain_category
(
  domain_id	NUMERIC(12,0)
		CONSTRAINT email_domain_category_dom_id
		  REFERENCES email_domain(domain_id),
  category	NUMERIC(6,0)
		CONSTRAINT email_domain_category_categ
		  REFERENCES email_domain_cat_code(code),
  CONSTRAINT email_domain_category_pk PRIMARY KEY (domain_id, category)
);
category:main/Oracle;
GRANT SELECT ON email_domain_category TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_domain_category TO read_mod_email;


/*	email_address



*/
category:main;
CREATE TABLE email_address
(
  address_id	NUMERIC(12,0)
		CONSTRAINT email_address_pk PRIMARY KEY,
  local_part	CHAR VARYING(128)
		NOT NULL,
  domain_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT email_address_domain_id
		  REFERENCES email_domain(domain_id),
  target_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT email_address_target_id
		  REFERENCES email_target(target_id),
  create_date	DATE
		NOT NULL,
  change_date	DATE,
  expire_date	DATE,
  CONSTRAINT email_address_unique UNIQUE (local_part, domain_id)
);
category:main/Oracle;
GRANT SELECT ON email_address TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_address TO read_mod_email;


-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --


/*	email_entity_domain

  Connection Entity -> Email domain.

  This can e.g. be used for specifying that persons/users belonging in
  OU X should get mail addresses in maildomain Y.

  Furthermore, one can use 'affiliation' to differentiate what
  maildomain to use for persons living in the same OU; students and
  employees could go in separate domains.

  TODO: Disallow registration of multiple domains on the same entity
        with NULL affiliation.

  As an example of how this table can be used, the below pseudocode
  illustrates the algorithm used to map from a user to that user's
  "official" maildomain at the University of Oslo:

    DEFAULT_MAILDOMAIN = 'ulrik.uio.no'
    try:
      ou_id, affiliation = <get from account_type with highest pri for USER>
    except <There are no account_type entries for USER>:
      return DEFAULT_MAILDOMAIN
    domain = <Look up domain_id corresponding to (ou_id, affiliation)>
    if domain is not None:
      return domain
    domain = <Look up domain_id corresponding to (ou_id, NULL)>
    if domain is not None:
      return domain
    return DEFAULT_DOMAIN

*/
category:main;
CREATE TABLE email_entity_domain
(
  entity_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT email_entity_domain_entity_id
		  REFERENCES entity_info(entity_id),
  affiliation	NUMERIC(6,0)
		CONSTRAINT email_entity_domain_affil
		  REFERENCES person_affiliation_code(code),
  domain_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT email_entity_domain_domain_id
		  REFERENCES email_domain(domain_id),
  CONSTRAINT email_entity_domain_u UNIQUE (entity_id, affiliation)
);
category:main/Oracle;
GRANT SELECT ON email_entity_domain TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_entity_domain TO read_mod_email;


/*	email_quota



*/
category:main;
CREATE TABLE email_quota
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_quota_pk PRIMARY KEY
		CONSTRAINT email_quota_target_id
		  REFERENCES email_target(target_id),
  quota_soft	NUMERIC(12,0)
		NOT NULL,
  quota_hard	NUMERIC(12,0)
		NOT NULL,
  CONSTRAINT email_quota_sizes CHECK (quota_soft < quota_hard)
);
category:main/Oracle;
GRANT SELECT ON email_quota TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_quota TO read_mod_email;


/*	email_spam_level_code



*/
category:code;
CREATE TABLE email_spam_level_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_spam_level_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_spam_level_codestr_u UNIQUE,
  grade		NUMERIC(4,0)
		NOT NULL
		CONSTRAINT email_spam_level_grade_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_spam_level_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_spam_level_code TO read_mod_email;


/*	email_spam_action_code



*/
category:code;
CREATE TABLE email_spam_action_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_spam_action_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_spam_action_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_spam_action_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_spam_action_code TO read_mod_email;


/*	email_spam_filter



*/
category:main;
CREATE TABLE email_spam_filter
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_spam_filter_pk PRIMARY KEY
		CONSTRAINT email_spam_filter_target_id
		  REFERENCES email_target(target_id),
  grade		NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_spam_filter_grade
		  REFERENCES email_spam_level_code(code),
  action	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_spam_filter_action
		  REFERENCES email_spam_action_code(code)
);
category:main/Oracle;
GRANT SELECT ON email_spam_filter TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_spam_filter TO read_mod_email;


/*	email_virus_found_code



*/
category:code;
CREATE TABLE email_virus_found_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_virus_found_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_virus_found_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_virus_found_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_virus_found_code TO read_mod_email;


/*	email_virus_removed_code



*/
category:code;
CREATE TABLE email_virus_removed_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_virus_removed_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_virus_removed_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON email_virus_removed_code TO read_mod_email;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_virus_removed_code TO read_mod_email;


/*	email_virus_scan



*/
category:main;
CREATE TABLE email_virus_scan
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_virus_scan_pk PRIMARY KEY
		CONSTRAINT email_virus_scan_target_id
		  REFERENCES email_target(target_id),
  found_action	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_virus_scan_found_action
		  REFERENCES email_virus_found_code(code),
  rem_action	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_virus_scan_rem_action
		  REFERENCES email_virus_removed_code(code),
  enable	CHAR(1)
		DEFAULT 'T'
		NOT NULL
		CONSTRAINT email_virus_scan_enable_bool
		  CHECK (enable IN ('T', 'F'))
);
category:main/Oracle;
GRANT SELECT ON email_virus_scan TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_virus_scan TO read_mod_email;


/*	email_forward

  TBD: Should we allow forwarding to be defined for other target
       types than users' personal mailboxes?

*/
category:main;
CREATE TABLE email_forward
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_forward_target_id
		  REFERENCES email_target(target_id),
  forward_to	CHAR VARYING(256)
		NOT NULL,
  enable	CHAR(1)
		DEFAULT 'F'
		NOT NULL
		CONSTRAINT email_forward_enable_bool
		  CHECK (enable IN ('T', 'F')),
  CONSTRAINT email_forward_pk PRIMARY KEY (target_id, forward_to)
);
category:main/Oracle;
GRANT SELECT ON email_forward TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_forward TO read_mod_email;


/*	email_vacation



*/
category:main;
CREATE TABLE email_vacation
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_vacation_target_id
		  REFERENCES email_target(target_id),
  start_date	DATE,
  vacation_text	CHAR VARYING(4000)
		NOT NULL,
  end_date	DATE,
  enable	CHAR(1)
		DEFAULT 'F'
		NOT NULL
		CONSTRAINT email_vacation_enable_bool
		  CHECK (enable IN ('T', 'F')),
  CONSTRAINT email_vacation_pk PRIMARY KEY (target_id, start_date)
);
category:main/Oracle;
GRANT SELECT ON email_vacation TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_vacation TO read_mod_email;


/*	email_primary_address



*/
category:main/Oracle;
ALTER TABLE email_address ADD (
  CONSTRAINT email_address_target_unique UNIQUE (address_id, target_id)
);

category:main/PostgreSQL;
CREATE UNIQUE INDEX email_address_target_unique
  ON email_address (address_id, target_id);


category:main;
CREATE TABLE email_primary_address
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_primary_address_pk PRIMARY KEY
		CONSTRAINT email_primary_address_target
		  REFERENCES email_target(target_id),
  address_id	NUMERIC(12,0)
		NOT NULL,
  CONSTRAINT email_primary_address_address
    FOREIGN KEY (address_id, target_id)
    REFERENCES email_address(address_id, target_id)
);
category:main/Oracle;
GRANT SELECT ON email_primary_address TO read_mod_email;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON email_primary_address TO read_mod_email;


/*	email_server_type_code

  Define the categories of (user retrieval/local delivery) email
  servers.

*/
category:code;
CREATE TABLE email_server_type_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_server_type_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_server_type_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	email_server

  Define the actual (user retrieval/local delivery) email servers.

*/
category:main;
CREATE TABLE email_server
(
  server_id	NUMERIC(12,0)
		CONSTRAINT email_server_host_id REFERENCES host_info(host_id)
		CONSTRAINT email_server_pk PRIMARY KEY,
  server_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_server_server_type
		  REFERENCES email_server_type_code(code)
);


/*

  Define which email server should be responsible for which email
  targets.

*/
category:main;
CREATE TABLE email_target_server
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_target_server_target_id
		  REFERENCES email_target(target_id),
  server_id	NUMERIC(12,0)
		CONSTRAINT email_target_server_server_id
		  REFERENCES email_server(server_id),
  CONSTRAINT email_target_server_pk PRIMARY KEY (target_id, server_id)
);


category:drop;
DROP TABLE email_target_server;
category:drop;
DROP TABLE email_server;
category:drop;
DROP TABLE email_server_type_code;
category:drop;
DROP TABLE email_primary_address;
category:drop/PostgreSQL;
DROP INDEX email_address_target_unique;
category:drop/Oracle;
ALTER TABLE email_address DROP CONSTRAINT email_address_target_unique;
category:drop;
DROP TABLE email_vacation;
category:drop;
DROP TABLE email_forward;
category:drop;
DROP TABLE email_virus_scan;
category:drop;
DROP TABLE email_virus_removed_code;
category:drop;
DROP TABLE email_virus_found_code;
category:drop;
DROP TABLE email_spam_filter;
category:drop;
DROP TABLE email_spam_action_code;
category:drop;
DROP TABLE email_spam_level_code;
category:drop;
DROP TABLE email_quota;
category:drop;
DROP TABLE email_entity_domain;
category:drop;
DROP TABLE email_address;
category:drop;
DROP TABLE email_domain_category;
category:drop;
DROP TABLE email_domain_cat_code;
category:drop;
DROP TABLE email_domain;
category:drop;
DROP TABLE email_target;
category:drop;
DROP TABLE email_target_code;
category:drop;
DROP SEQUENCE email_id_seq;

category:drop/Oracle;
DROP ROLE change_mod_email;
category:drop/Oracle;
DROP ROLE read_mod_email;
