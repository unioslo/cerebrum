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


category:code/Oracle;
CREATE ROLE read_mod_posix_user NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_posix_user NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_posix_user TO change_mod_posix_user;

category:code/Oracle;
GRANT read_mod_posix_user TO read_core_table;
category:code/Oracle;
GRANT change_mod_posix_user TO change_core_table;


category:code;
CREATE TABLE posix_shell_code
(
  code		NUMERIC(6,0)
		CONSTRAINT posix_shell_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT posix_shell_codestr_u UNIQUE,
  /* Longer shell strings are possible, but not very likely... */
  shell		CHAR VARYING(512)
		NOT NULL
		CONSTRAINT posix_shell_code_shell_u UNIQUE
);
category:code/Oracle;
GRANT SELECT ON posix_shell_code TO read_mod_posix_user;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON posix_shell_code TO read_mod_posix_user;


/*	posix_group

  Extra information for groups that exist as POSIX (file) groups.

  Names of POSIX groups are registered in entity_name (with any
  value_domain_code the installation thinks appropriate for group
  names).  This implies that any business rules for length etc. of
  user names are handled outside the database.

  Even though POSIX groups can have passwords associated with them,
  this is very rare and hence not supported by this module.

  gid
	Unix numeric filegroup ID.

 */
category:main;
CREATE TABLE posix_group
(
  group_id	NUMERIC(12,0)
		CONSTRAINT posix_group_pk PRIMARY KEY
		CONSTRAINT posix_group_group_id
		  REFERENCES group_info(group_id),
  posix_gid	NUMERIC(12,0)
		NOT NULL
                CONSTRAINT posix_group_gid_chk
                  CHECK (posix_gid >= 0 AND posix_gid <= 2147483647)
		CONSTRAINT posix_group_gid UNIQUE
);
category:main/Oracle;
GRANT SELECT ON posix_group TO read_mod_posix_user;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON posix_group TO read_mod_posix_user;


category:main;
CREATE SEQUENCE posix_gid_seq [:sequence_start value=1000];
category:main/Oracle;
GRANT SELECT ON posix_gid_seq TO read_mod_posix_user;


/*	posix_user

  Names of POSIX users are registered in entity_name (with any
  value_domain_code the installation thinks appropriate for user
  names).  This implies that any business rules for length etc. of
  user names are handled outside the database.

  'gecos'	For personal users the POSIX gecos field will default
		to the owning persons full name.  The default can be
		overridden by setting this column non-NULL.
		For non-personal users this column must be non-NULL.

*/
category:main;
CREATE TABLE posix_user (
  account_id    NUMERIC(12,0)
		CONSTRAINT posix_user_pk PRIMARY KEY
                CONSTRAINT posix_user_account_id
                  REFERENCES account_info(account_id),
  posix_uid     NUMERIC(12,0)
		NOT NULL
                CONSTRAINT posix_user_uid_chk
                  CHECK (posix_uid >= 0 AND posix_uid <= 2147483647)
		CONSTRAINT posix_user_uid_unique UNIQUE,
  gid           NUMERIC(12,0)
		NOT NULL
                CONSTRAINT posix_user_gid
                  REFERENCES posix_group(group_id),
  pg_member_op	NUMERIC(6,0)
		DEFAULT [:get_constant name=group_memberop_union]
		NOT NULL
		CONSTRAINT posix_user_pg_member_op_chk
		  CHECK (pg_member_op =
			 [:get_constant name=group_memberop_union]),
  /* Longer GECOS strings are possible, but not very likely... */
  gecos		CHAR VARYING(512),
  /* Longer home dirs are possible, but not very likely...

     Not sure if NULL should should be allowed, but we're allowing it
     for now; maybe someone needs to keep "home == '/'" and "home not
     specified" cases separate. */
  home		CHAR VARYING(512),
  shell		NUMERIC(6,0)
		NOT NULL
		CONSTRAINT posix_user_shell REFERENCES posix_shell_code(code),
  /* Note that the following constraint does not really *guarantee*
     that account 'account_id' is a member of group 'gid', as other
     "intersection" or "difference" member might be "in the way". */
  CONSTRAINT posix_user_in_primary_group
    FOREIGN KEY (gid, pg_member_op, account_id)
    REFERENCES group_member(group_id, operation, member_id)
);
category:main/Oracle;
GRANT SELECT ON posix_user TO read_mod_posix_user;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON posix_user TO read_mod_posix_user;


category:main;
CREATE SEQUENCE posix_uid_seq [:sequence_start value=1000];
category:main/Oracle;
GRANT SELECT ON posix_uid_seq TO read_mod_posix_user;


category:drop;
DROP TABLE posix_user;
category:drop;
DROP TABLE posix_group;
category:drop;
DROP TABLE posix_shell_code;
category:drop;
DROP SEQUENCE posix_uid_seq;
category:drop;
DROP SEQUENCE posix_gid_seq;

category:drop/Oracle;
DROP ROLE change_mod_posix_user;
category:drop/Oracle;
DROP ROLE read_mod_posix_user;
