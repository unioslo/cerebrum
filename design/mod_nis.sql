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
CREATE ROLE read_mod_nis NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_nis NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_nis TO read_core_table;
category:code/Oracle;
GRANT change_mod_nis TO change_core_table;


category:code;
CREATE TABLE nis_domain_code
(
  code		NUMERIC(6,0)
		CONSTRAINT nis_domain_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT nis_domain_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);
category:code/Oracle;
GRANT SELECT ON nis_domain_code TO read_mod_nis;
category:code/Oracle;
GRANT INSERT, UPDATE, DELETE ON nis_domain_code TO read_mod_nis;


category:main;
CREATE TABLE nis_netgroup
(
  domain	NUMERIC(6,0)
		CONSTRAINT nis_netgroup_domain
		  REFERENCES nis_domain_code(code),
  group_id	NUMERIC(12,0)
		CONSTRAINT nis_netgroup_group_id
		  REFERENCES group_info(group_id),
  CONSTRAINT nis_netgroup_pk PRIMARY KEY (domain, group_id)
);
category:main/Oracle;
GRANT SELECT ON nis_netgroup TO read_mod_nis;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON nis_netgroup TO read_mod_nis;


/*

  Should we have similar "export to domain x" tables for users?  File
  groups?

*/
category:drop;
DROP TABLE nis_netgroup;
category:drop;
DROP TABLE nis_domain_code;

category:drop/Oracle;
DROP ROLE change_mod_nis;
category:drop/Oracle;
DROP ROLE read_mod_nis;
