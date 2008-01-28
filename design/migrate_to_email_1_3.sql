/*
 * Copyright 2007 University of Oslo, Norway
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
 */

/* SQL script for migrating a mod_email 1.2 to 1.3 */

category:pre;
DROP SEQUENCE email_id_seq;

/* Drop almost all constraints. Put them back in after convertion. */

/* email_target */
category:pre;
CREATE TABLE tmp_email_target
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type		NUMERIC(6,0)
			DEFAULT [:get_constant name=entity_email_target]
			NOT NULL
			CONSTRAINT email_target_entity_type_chk
			  CHECK (entity_type = [:get_constant name=entity_email_target]),
  target_id		NUMERIC(12,0),
  target_type		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT email_target_target_type
			  REFERENCES email_target_code(code),
  target_entity_type	NUMERIC(6,0),
  target_entity_id	NUMERIC(12,0),
  alias_value		CHAR VARYING(512),
  using_uid		NUMERIC(12,0)
			CONSTRAINT email_target_using_uid
			  REFERENCES posix_user(account_id),
  server_id		NUMERIC(12,0)
			CONSTRAINT email_target_server_server_id
			  REFERENCES email_server(server_id)
);

/* email_address */
category:pre;
CREATE TABLE tmp_email_domain
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_email_domain]
		NOT NULL
		CONSTRAINT email_domain_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_email_domain]),
  domain_id	NUMERIC(12,0),
  domain	CHAR VARYING(128)
		NOT NULL,
  description	CHAR VARYING(512)
		NOT NULL
);

/* email_domain */

category:pre;
CREATE TABLE tmp_email_address
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_email_address]
		NOT NULL
		CONSTRAINT email_address_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_email_address]),
  address_id	NUMERIC(12,0)
		NOT NULL,
  local_part	CHAR VARYING(128)
		NOT NULL,
  domain_id	NUMERIC(12,0)
		NOT NULL,
  target_id	NUMERIC(12,0)
		NOT NULL,
  create_date	DATE
		NOT NULL,
  change_date	DATE,
  expire_date	DATE
);

category:pre;
ALTER TABLE email_address DROP CONSTRAINT email_address_domain_id;
category:pre;
ALTER TABLE email_address DROP CONSTRAINT email_address_target_id;

/* ------------------------------------------------------------- */

/* tables dependant of the three converted tables. */

category:pre;
ALTER TABLE email_entity_domain DROP CONSTRAINT email_entity_domain_domain_id;
category:pre;
ALTER TABLE email_entity_domain ADD tmp_domain_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_quota DROP CONSTRAINT email_quota_target_id;
category:pre;
ALTER TABLE email_quota ADD tmp_target_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_spam_filter DROP CONSTRAINT email_spam_filter_target_id;
category:pre;
ALTER TABLE email_spam_filter ADD tmp_target_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_virus_scan DROP CONSTRAINT email_virus_scan_target_id;
category:pre;
ALTER TABLE email_virus_scan ADD tmp_target_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_forward DROP CONSTRAINT email_forward_target_id;
category:pre;
ALTER TABLE email_forward ADD tmp_target_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_vacation DROP CONSTRAINT email_vacation_target_id;
category:pre;
ALTER TABLE email_vacation ADD tmp_target_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_primary_address DROP CONSTRAINT email_primary_address_address;
category:pre;
ALTER TABLE email_primary_address DROP CONSTRAINT email_primary_address_target;
category:pre;
ALTER TABLE email_primary_address ADD tmp_target_id NUMERIC(12,0);
category:pre;
ALTER TABLE email_primary_address ADD tmp_address_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_domain_category DROP CONSTRAINT email_domain_category_dom_id;
category:pre;
ALTER TABLE email_domain_category ADD tmp_domain_id NUMERIC(12,0);

category:pre;
ALTER TABLE email_target_filter DROP CONSTRAINT email_target_filter_target_id;
category:pre;
ALTER TABLE email_target_filter ADD tmp_target_id NUMERIC(12,0);

/* ------------------------------------------------------------- */
/* End mid-convertion. */
/* ------------------------------------------------------------- */


/* email_domain */
category:post;
DROP TABLE email_domain;
category:post;
ALTER TABLE tmp_email_domain RENAME TO email_domain;
category:post;
ALTER TABLE email_domain ADD
  CONSTRAINT email_domain_pk 
    PRIMARY KEY (domain_id);
category:post;
ALTER TABLE email_domain ADD
  CONSTRAINT email_domain_entity_id
    FOREIGN KEY (entity_type, domain_id)
    REFERENCES entity_info(entity_type, entity_id);
category:post;
ALTER TABLE email_domain ADD
  CONSTRAINT email_domain_domain_u 
    UNIQUE (domain);

/* email_target */
category:post;
DROP TABLE email_target;
category:post;
ALTER TABLE tmp_email_target RENAME TO email_target;
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_pk 
    PRIMARY KEY (target_id);
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_entity_id
    FOREIGN KEY (entity_type, target_id)
    REFERENCES entity_info(entity_type, entity_id);
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_target_entity_id 
    FOREIGN KEY (target_entity_type, target_entity_id)
    REFERENCES entity_info(entity_type, entity_id);
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_target_entity_type
    CHECK (target_entity_type IS NULL OR
	   target_entity_type IN ([:get_constant name=entity_account],
			          [:get_constant name=entity_group]));
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_alias_u 
    UNIQUE (using_uid, alias_value);
category:post;
ALTER TABLE email_target ADD 
  CONSTRAINT email_target_entity_server_u 
    UNIQUE (target_entity_id, server_id);

/* email_address */
category:post;
DROP TABLE email_address;
category:post;
ALTER TABLE tmp_email_address RENAME TO email_address;
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_pk 
    PRIMARY KEY (address_id);
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_domain_id
    FOREIGN KEY (domain_id)
    REFERENCES email_domain(domain_id);
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_entity_id
    FOREIGN KEY (entity_type, address_id)
    REFERENCES entity_info(entity_type, entity_id);
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_unique UNIQUE (local_part, domain_id);
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_caseless_chk
    CHECK (local_part = LOWER(local_part));
category:post;
ALTER TABLE email_address ADD 
  CONSTRAINT email_address_target_unique 
    UNIQUE (address_id, target_id);


/* ------------------------------------------------------------- */

/* tables dependant of the three converted tables. */

category:post2;
ALTER TABLE email_entity_domain DROP COLUMN domain_id;
category:post2;
ALTER TABLE email_entity_domain RENAME tmp_domain_id TO domain_id;
category:post2;
ALTER TABLE email_entity_domain ADD
  CONSTRAINT email_entity_domain_domain_id
    FOREIGN KEY (domain_id)
    REFERENCES email_domain(domain_id);

category:post2;
ALTER TABLE email_quota DROP COLUMN target_id;
category:post2;
ALTER TABLE email_quota RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_quota ADD
  CONSTRAINT email_quota_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_quota ADD
  CONSTRAINT email_quota_pk 
    PRIMARY KEY (target_id);

category:post2;
ALTER TABLE email_spam_filter DROP COLUMN target_id;
category:post2;
ALTER TABLE email_spam_filter RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_spam_filter ADD
  CONSTRAINT email_spam_filter_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_spam_filter ADD
  CONSTRAINT email_spam_filter_pk 
    PRIMARY KEY (target_id);

category:post2;
ALTER TABLE email_virus_scan DROP COLUMN target_id;
category:post2;
ALTER TABLE email_virus_scan RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_virus_scan ADD
  CONSTRAINT email_virus_scan_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_virus_scan ADD
  CONSTRAINT email_virus_scan_pk 
    PRIMARY KEY (target_id);

category:post2;
ALTER TABLE email_forward DROP COLUMN target_id;
category:post2;
ALTER TABLE email_forward RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_forward ADD
  CONSTRAINT email_forward_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_forward ADD
  CONSTRAINT email_forward_pk 
    PRIMARY KEY (target_id, forward_to);

category:post2;
ALTER TABLE email_vacation DROP COLUMN target_id;
category:post2;
ALTER TABLE email_vacation RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_vacation ADD
  CONSTRAINT email_vacation_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_vacation ADD
  CONSTRAINT email_vacation_pk 
    PRIMARY KEY (target_id, start_date);

category:post2;
ALTER TABLE email_domain_category DROP COLUMN domain_id;
category:post2;
ALTER TABLE email_domain_category RENAME tmp_domain_id TO domain_id;
category:post2;
ALTER TABLE email_domain_category ADD
  CONSTRAINT email_domain_category_dom_id
    FOREIGN KEY (domain_id)
    REFERENCES email_domain(domain_id);
category:post2;
ALTER TABLE email_domain_category ADD
  CONSTRAINT email_domain_category_pk 
    PRIMARY KEY (domain_id, category);

category:post2;
ALTER TABLE email_primary_address DROP COLUMN target_id;
category:post2;
ALTER TABLE email_primary_address DROP COLUMN address_id;
category:post2;
ALTER TABLE email_primary_address RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_primary_address RENAME tmp_address_id TO address_id;
category:post2;
ALTER TABLE email_primary_address ALTER address_id SET NOT NULL;
category:post2;
ALTER TABLE email_primary_address ADD
  CONSTRAINT email_primary_address_pk 
    PRIMARY KEY (target_id);
category:post2;
ALTER TABLE email_primary_address ADD
  CONSTRAINT email_primary_address_target
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_primary_address ADD
  CONSTRAINT email_primary_address_address
    FOREIGN KEY (address_id, target_id)
    REFERENCES email_address(address_id, target_id);

category:post2;
ALTER TABLE email_target_filter DROP COLUMN target_id;
category:post2;
ALTER TABLE email_target_filter RENAME tmp_target_id TO target_id;
category:post2;
ALTER TABLE email_target_filter ADD
  CONSTRAINT email_target_filter_target_id
    FOREIGN KEY (target_id)
    REFERENCES email_target(target_id);
category:post2;
ALTER TABLE email_target_filter ADD
  CONSTRAINT email_target_filter_pk
    PRIMARY KEY (target_id, filter);
