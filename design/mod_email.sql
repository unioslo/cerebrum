/*	email_target_code

  Define valid target types, e.g. 'user', 'pipe', 'file', 'Mailman'.

*/
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


/*	email_target

  Define all targets this email system should know about.

  TBD: For (at least) `pipe` and `file` targets it is necessary to
       specify which user the delivery should be done as; how should
       we encode such information?

  TBD: How should "user target -> specific IMAP server" info be
       modelled?

*/
CREATE TABLE email_target
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_target_pk PRIMARY KEY,
  target_type	NUMERIC(6,0)
		CONSTRAINT email_target_target_type
		  REFERENCES email_target_code(code),
  entity_type	NUMERIC(6,0),
  entity_id	NUMERIC(12,0),
  alias_value	CHAR VARYING(1024),
  CONSTRAINT email_destination_entity FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT email_destination_entity_type
    CHECK (entity_type IN ([:get_constant name=entity_account],
			   [:get_constant name=entity_group])),
  CONSTRAINT email_target_ambiguous
    CHECK ((entity_id IS NOT NULL AND alias_value IS NULL) OR
           (entity_id IS NULL AND alias_value IS NOT NULL))
);


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


/*	email_domain



*/
CREATE TABLE email_domain
(
  domain_id	NUMERIC(6,0)
		CONSTRAINT email_domain_pk PRIMARY KEY,
  domain	CHAR VARYING(128)
		NOT NULL
		CONSTRAINT email_domain_domain_u UNIQUE,
  category	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_domain_category
		  REFERENCES email_domain_cat_code(code),
  description	CHAR VARYING(512)
		NOT NULL
);


/*	email_address



*/
CREATE TABLE email_address
(
  address_id	NUMERIC(12,0)
		CONSTRAINT email_address_pk PRIMARY KEY,
  local_part	CHAR VARYING(128)
		NOT NULL,
  domain_id	NUMERIC(6,0)
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


-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --


/*	email_entity_domain

  Connection Entity -> Email domain.  Useful for specifying that OU x
  lives in mail domain Y.

  TBD: It's likely that persons living in the same OU should have
       different mail domains, e.g. based on the kind of affiliation
       they have with the OU.  Should something like the
       `person_affiliation_code` table be mixed into this table, or
       would we rather want it to stay `entity_type` neutral?

*/
CREATE TABLE email_entity_domain
(
  entity_id	NUMERIC(12,0)
		CONSTRAINT email_entity_domain_pk PRIMARY KEY,
  entity_type	NUMERIC(6,0)
		NOT NULL,
  domain_id	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT email_entity_domain_domain_id
		  REFERENCES email_domain(domain_id),
  CONSTRAINT email_entity_domain_entity FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*	email_quota



*/
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


/*	email_spam_level_code



*/
CREATE TABLE email_spam_level_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_spam_level_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_spam_level_codestr_u UNIQUE,
  level		NUMERIC(4,0)
		NOT NULL
		CONSTRAINT email_spam_level_level_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);


/*	email_spam_action_code



*/
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


/*	email_spam_filter



*/
CREATE TABLE email_spam_filter
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_spam_filter_pk PRIMARY KEY
		CONSTRAINT email_spam_filter_target_id
		  REFERENCES email_target(target_id),
  level		NUMERIC(6,0)
		CONSTRAINT email_spam_filter_level
		  REFERENCES email_spam_level_code(code),
  action	NUMERIC(6,0)
		CONSTRAINT email_spam_filter_action
		  REFERENCES email_spam_action_code(code)
);


/*	email_virus_found_code



*/
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


/*	email_virus_removed_code



*/
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


/*	email_virus_scan



*/
CREATE TABLE email_virus_scan
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_virus_scan_pk PRIMARY KEY
		CONSTRAINT email_virus_scan_target_id
		  REFERENCES email_target(target_id),
  found_action	NUMERIC(6,0)
		CONSTRAINT email_virus_scan_found_action
		  REFERENCES email_virus_found_code(code),
  rem_action	NUMERIC(6,0)
		CONSTRAINT email_virus_scan_rem_action
		  REFERENCES email_virus_removed_code(code),
  enable	CHAR(1)
		DEFAULT 'T'
		NOT NULL
		CONSTRAINT email_virus_scan_enable_bool
		  CHECK (enable IN ('T', 'F'))
);


/*	email_forward

  TBD: Should we allow forwarding to be defined for other target
       types than users' personal mailboxes?

*/
CREATE TABLE email_forward
(
  account_id	NUMERIC(12,0)
		CONSTRAINT email_forward_account_id
		  REFERENCES account_info(account_id),
  forward_to	CHAR VARYING(256)
		NOT NULL,
  enable	CHAR(1)
		DEFAULT 'F'
		NOT NULL
		CONSTRAINT email_forward_enable_bool
		  CHECK (enable IN ('T', 'F')),
  CONSTRAINT email_forward_pk PRIMARY KEY (account_id, forward_to)
);


/*	email_vacation



*/
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


/*	email_primary_address



*/
CREATE UNIQUE INDEX email_address_target_unique
  ON email_address (address_id, target_id);

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
