CREATE TABLE posix_shell
(
  shell		CHAR VARYING(16)
		CONSTRAINT posix_shell_pk PRIMARY KEY,
  shell_path	CHAR VARYING(64)
		NOT NULL,
  CONSTRAINT posix_shell_path_unique UNIQUE (shell_path)
);


/*	posix_user

  There are several reasons for having separate '*_domain'-columns for
  name, uid and gid:

   * This is necessary if e.g. 'name' should be separately unique in
     NIS domain X and Y, while 'uid' should be unique across both of
     these NIS domains.

   * It's useful to allow separate reservation of user names, uids and
     gids (as these reservations are coupled to the same "value
     domain" names.

  TBD: Holder argumentasjonen over, eller er det bedre å bruke kun en
       kolonne for å indikere verdi-domene for alle tre verdiene?

  'gecos'	For personal users the POSIX gecos field will default
		to the owning persons full name.  The default can be
		overridden by setting this column non-NULL.
		For non-personal users this column must be non-NULL.

*/
CREATE TABLE posix_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT posix_user_account_id
		  REFERENCES account(account_id)
		CONSTRAINT posix_user_pk PRIMARY KEY,
/* TBD: Bør det tillates at samme `account' gis opphav til flere
        `posix_user's, f.eks. dersom man opererer med multiple
        NIS-domener?  Hvis ja: Hva bør da primærnøkkelen for
        posix_user være? */
/* TBD: Bør vi støtte POSIX-brukernavn på mer enn 8 tegn? */
  name		CHAR VARYING(16)
		NOT NULL
		CONSTRAINT posix_user_name_length CHECK (LENGTH(name) <= 8),
  name_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_name_domain
		  REFERENCES value_domain_code(code),
  uid		NUMERIC(10,0)
		NOT NULL,
  uid_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_uid_domain
		  REFERENCES value_domain_code(code),
  gid		NUMERIC(10,0)
		NOT NULL,
  gid_domain	CHAR VARYING(16)
		CONSTRAINT posix_user_gid_domain
		  REFERENCES value_domain_code(code),
  gecos		CHAR VARYING(128),
  dir		CHAR VARYING(64)
		NOT NULL,
  shell		CHAR VARYING(16)
		NOT NULL
		CONSTRAINT posix_user_shell REFERENCES posix_shell(shell),
  CONSTRAINT posix_user_name_unique UNIQUE(name, name_domain),
  CONSTRAINT posix_user_uid_unique UNIQUE(uid, uid_domain),
  CONSTRAINT posix_user_gid_unique UNIQUE(gid, gid_domain)
);


/* TBD: Spread for brukere; bør dette implementeres ved hjelp av en
	"REFERENCES account(account_id)"-type tabell, eller som
	separat spread-tabell for hver enkelt variant av bruker det
	finnes andre tabeller for (som f.eks. posix_user)? */


/*

Extra information for groups exported as NIS filegroups.

Note that the names of NIS filegroups can't be longer than 8
character; if a group with too long a name is referenced in this
table, it should be ignored by the export machinery.

   gid
	Unix numeric filegroup ID.
 */
CREATE TABLE nis_filegroup
(
  gkey		NUMERIC(12,0)
		CONSTRAINT nis_filegroup_pk PRIMARY KEY
		CONSTRAINT nis_filegroup_gkey REFERENCES group_info(group_id),
  gid		NUMERIC(5,0)
		CONSTRAINT nis_filegroup_gid UNIQUE
);
