/*
 * Copyright 2003 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 */

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
	
category:drop;
DROP TABLE mount_host;
category:drop;
DROP TABLE mount_host_type_code;

/* arch-tag: f2eaf07f-2347-408d-b880-f54354f01d57
   (do not change this comment) */
