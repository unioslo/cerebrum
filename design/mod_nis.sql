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

/*

  Should we have similar "export to domain x" tables for users?  File
  groups?

*/
