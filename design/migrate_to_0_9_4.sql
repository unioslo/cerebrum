/* SQL script for migrating a 0.9.3 database to 0.9.4
*/
category:pre;
CREATE TABLE homedir (
  homedir_id	NUMERIC(12,0)
		CONSTRAINT homedir_pk PRIMARY KEY,
  account_id	NUMERIC(12,0) NOT NULL
		CONSTRAINT homedir_account_id
		  REFERENCES account_info(account_id),
  home		CHAR VARYING(512),
  disk_id	NUMERIC(12,0)
		CONSTRAINT account_home_disk_id REFERENCES disk_info(disk_id),
  status	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT account_home_status
		  REFERENCES home_status_code(code),
  CONSTRAINT homedir_chk
    CHECK ((home IS NOT NULL AND disk_id IS NULL) OR
	   (home IS NULL AND disk_id IS NOT NULL)),
  CONSTRAINT homedir_ac_hid_u UNIQUE (homedir_id, account_id),
  CONSTRAINT homedir_ac_home_u UNIQUE (homedir_id, home),
  CONSTRAINT homedir_ac_disk_u UNIQUE (homedir_id, disk_id)
);
category:pre;
ALTER TABLE account_home   ADD COLUMN
  homedir_id	NUMERIC(12,0);
category:pre;
CREATE SEQUENCE homedir_id_seq;

category:post;
ALTER TABLE account_home DROP COLUMN home;
category:post;
ALTER TABLE account_home DROP COLUMN disk_id;
category:post;
ALTER TABLE account_home DROP COLUMN status;
category:post;
ALTER TABLE account_home ALTER COLUMN homedir_id SET NOT NULL;
category:post;
ALTER TABLE account_home ADD CONSTRAINT account_home_homedir
    FOREIGN KEY(homedir_id, account_id) REFERENCES 
    homedir(homedir_id, account_id);

/* arch-tag: 7f7ee4c6-d53d-4206-bea5-89c8a9f45a5c
   (do not change this comment) */
