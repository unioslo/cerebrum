/* encoding: utf-8
 *
 * Copyright 2015-2019 University of Oslo, Norway
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
 *
 * Tables used by Cerebrum.modules.virtualgroup.OUGroup
 *
 * Depends on mod_virtualgroup
 */
category:metainfo;
name=virtual_group_ou;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE virtual_group_ou;

category:drop;
DROP TABLE virtual_group_ou_recursion_code;

category:drop;
DROP TABLE virtual_group_ou_membership_type_code;


/*
*/
category:code;
CREATE TABLE virtual_group_ou_recursion_code
(
  code
    NUMERIC(6,0)
    PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*
 * TBD: Move into mod_virtual_group?
 * member types:
 * person
 * primary account (quasi person)
 * all accounts with account type
 * ...
 */
category:code;
CREATE TABLE virtual_group_ou_membership_type_code
(
  code
    NUMERIC(6,0)
    PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  virtual_group_ou
 *
 * Use OUs as source for group memberships
*/
category:main;
CREATE TABLE virtual_group_ou
(
  group_id
    NUMERIC(12,0)
    CONSTRAINT virtual_group_ou_pk PRIMARY KEY
    CONSTRAINT virtual_group_ou_info_fk
      REFERENCES virtual_group_info,

  ou_id
    NUMERIC(12,0)
    NOT NULL
    REFERENCES ou_info(ou_id),

  /* null means any for these fields */
  affiliation
    NUMERIC(6,0)
    NULL
    REFERENCES person_affiliation_code,

  affiliation_source
    NUMERIC(6,0)
    NULL
    REFERENCES authoritative_system_code,

  affiliation_status
    NUMERIC(6,0)
    NULL
    REFERENCES person_aff_status_code(status),

  /* how recursion is applied */
  recursion
    NUMERIC(6,0)
    NOT NULL
    REFERENCES virtual_group_ou_recursion_code,

  /* null only if recursion is not defined */
  ou_perspective
    NUMERIC(6,0)
    NULL
    REFERENCES ou_perspective_code,

  /* membership types (person, primary account, accounts by account_type) */
  member_type
    NUMERIC(6,0)
    NOT NULL
    REFERENCES virtual_group_ou_membership_type_code
);

category:main;
CREATE INDEX virtual_group_ou_aff_index
  ON virtual_group_ou(ou_id, recursion, affiliation);

category:main;
CREATE INDEX virtual_group_ou_total_index
  ON virtual_group_ou(ou_id, affiliation, affiliation_source,
    affiliation_status, recursion, ou_perspective, member_type);

category:main;
CREATE INDEX virtual_group_ou_nopers_index
  ON virtual_group_ou(ou_id, affiliation, affiliation_source,
    affiliation_status, recursion, member_type);

category:main;
CREATE INDEX virtual_group_ou_nosrc_index
  ON virtual_group_ou(ou_id, affiliation, recursion, ou_perspective,
    member_type);
