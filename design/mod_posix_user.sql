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
CREATE TABLE posix_group
(
  group_id	NUMERIC(12,0)
		CONSTRAINT posix_group_pk PRIMARY KEY
		CONSTRAINT posix_group_group_id
		  REFERENCES group_info(group_id),
  gid		NUMERIC(12,0)
                CONSTRAINT posix_group_gid_chk
                  CHECK (gid >= 0 AND gid < 2147483648)
		CONSTRAINT posix_group_gid UNIQUE
);


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
CREATE TABLE posix_user (
  account_id    NUMERIC(12,0)
		CONSTRAINT posix_user_pk PRIMARY KEY
                CONSTRAINT posix_user_account_id
                  REFERENCES account_info(account_id),
  uid           NUMERIC(12,0)
		NOT NULL
                CONSTRAINT posix_user_uid_chk
                  CHECK (uid >= 0 AND uid < 2147483648)
		CONSTRAINT posix_user_uid_unique UNIQUE,
  gid           NUMERIC(12,0)
		NOT NULL
                CONSTRAINT posix_user_gid
                  REFERENCES posix_group(group_id),
  /* Longer GECOS strings are possible, but not very likely... */
  gecos		CHAR VARYING(512),
  /* Longer home dirs are possible, but not very likely...

     Not sure if NULL should should be allowed, but we're allowing it
     for now; maybe someone needs to keep "home == '/'" and "home not
     specified" cases separate. */
  home		CHAR VARYING(512),
  shell		NUMERIC(6,0)
		NOT NULL
		CONSTRAINT posix_user_shell REFERENCES posix_shell_code(code)
);
CREATE SEQUENCE uid_seq START WITH 1000;
