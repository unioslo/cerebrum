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
