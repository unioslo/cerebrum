/* SQL script for migrating a pre 0.9.2 database to 0.9.2
*/
category:pre;
CREATE TABLE home_status_code (
  code          NUMERIC(6,0)
                CONSTRAINT home_status_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT home_status_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

category:pre;
CREATE TABLE account_home (
  account_id    NUMERIC(12,0)
                CONSTRAINT account_home_fk 
                REFERENCES account_info(account_id),
  spread        NUMERIC(6,0) NOT NULL
		CONSTRAINT account_home_spread
		  REFERENCES spread_code(code),
  home          CHAR VARYING(512),
  disk_id       NUMERIC(12,0)
                CONSTRAINT account_info_disk_id REFERENCES disk_info(disk_id),
  status        NUMERIC(6,0) NOT NULL
                CONSTRAINT home_status_code
                  REFERENCES home_status_code(code),
  CONSTRAINT account_home_pk
    PRIMARY KEY (account_id, spread)
);

category:pre;
CREATE TABLE cerebrum_metainfo (
  name		CHAR VARYING(80)
		CONSTRAINT cerebrum_metainfo_pk PRIMARY KEY,
  value		CHAR VARYING(1024) NOT NULL
);

category:post;
ALTER TABLE account_info DROP COLUMN disk_id;
category:post;
ALTER TABLE account_info DROP COLUMN home;
