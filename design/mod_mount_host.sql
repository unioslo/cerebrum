category:code;
CREATE TABLE mount_host_type_code(
  code		NUMERIC(6,0)
		CONSTRAINT mount_host_type_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT mount_host_type_code_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);

category:main;
CREATE TABLE mount_host
(
  mount_host_id NUMERIC(12,0) CONSTRAINT mount_host_pk PRIMARY KEY,
  mount_type    NUMERIC(6,0)
		CONSTRAINT mount_host_type
		  REFERENCES mount_host_type_code(code),
  host_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT mount_host_host_id
		  REFERENCES host_info(host_id),
  mount_name    CHAR VARYING(80)
		NOT NULL
);

	
