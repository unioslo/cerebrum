/*  host_info

   name is the DNS name that one must log into to get access to the
   machines disks.

*/

CREATE TABLE host_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT 2005
		NOT NULL
		CONSTRAINT host_info_entity_type_chk
		  CHECK (entity_type = 2005),
  host_id	NUMERIC(6,0)
		CONSTRAINT host_info_entity_id 
		  REFERENCES entity_info(entity_id),
  name		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT host_name_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);

/* disk_info

  path is the name of the directory that users are placed in and that
       will ocour in the NIS map, excluding trailing slash.  
*/

CREATE TABLE disk_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT 2006
		NOT NULL
		CONSTRAINT host_info_entity_type_chk
		  CHECK (entity_type = 2006),
  disk_id	NUMERIC(6,0)
		CONSTRAINT disk_info_entity_id 
		  REFERENCES entity_info(entity_id),
  host_id	NUMERIC(6,0)
		NULL
		CONSTRAINT disk_host_id
		  REFERENCES host(host_id),
  path		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT disk_info_name_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);

