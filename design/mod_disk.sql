/*  host_info

   name is the DNS name that one must log into to get access to the
   machines disks.

*/

category:main;
CREATE TABLE host_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_host]
		NOT NULL
		CONSTRAINT host_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_host]),
  host_id	NUMERIC(6,0) 
                CONSTRAINT host_host_id_pk PRIMARY KEY,
  name		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT host_name_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT host_info_entity_id 
    FOREIGN KEY (entity_type, host_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* disk_info

  path is the name of the directory that users are placed in and that
       will ocour in the NIS map, excluding trailing slash.  
*/

category:main;
CREATE TABLE disk_info
(
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_disk]
		NOT NULL
		CONSTRAINT host_info_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_disk]),
  disk_id	NUMERIC(6,0)
                CONSTRAINT disk_disk_id_pk PRIMARY KEY,
  host_id	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT disk_host_id
		  REFERENCES host_info(host_id),
  path		CHAR VARYING(80)
		NOT NULL
		CONSTRAINT disk_info_name_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT disk_info_entity_id 
    FOREIGN KEY (entity_type, disk_id)
    REFERENCES entity_info(entity_type, entity_id)
);

category:drop;
DROP TABLE disk_info;
category:drop;
DROP TABLE host_info;
