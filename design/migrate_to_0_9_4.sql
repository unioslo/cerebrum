/* SQL script for migrating a 0.9.3 database to 0.9.4
*/
category:pre;
CREATE TABLE homedir (
  homedir_id	NUMERIC(12,0)
		CONSTRAINT homedir_pk PRIMARY KEY,
  home		CHAR VARYING(512),
  disk_id	NUMERIC(12,0)
		CONSTRAINT account_home_disk_id REFERENCES disk_info(disk_id),
  status	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT account_home_status
		  REFERENCES home_status_code(code),
  CONSTRAINT homedir_chk
    CHECK ((home IS NOT NULL AND disk_id IS NULL) OR
	   (home IS NULL AND disk_id IS NOT NULL))
);
category:pre;
ALTER TABLE account_home   ADD COLUMN
homedir_id	NUMERIC(12,0)
		CONSTRAINT account_home_homedir REFERENCES homedir(homedir_id);

category:post;
ALTER TABLE account_home DROP COLUMN home;
category:post;
ALTER TABLE account_home DROP COLUMN disk_id;
category:post;
ALTER TABLE account_home DROP COLUMN status;
category:post;
ALTER TABLE account_home ALTER COLUMN homedir_id SET NOT NULL;
