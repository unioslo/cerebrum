/*
 * Copyright 2004 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.4 database to 0.9.5
*/


/* Insert entity_external_id_code */
category:pre;
CREATE TABLE entity_external_id_code
(
  code		NUMERIC(6,0)
		CONSTRAINT entity_external_id_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL,
  entity_type	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT entity_external_id_code_entity_type
		  REFERENCES entity_type_code(code),
  description	CHAR VARYING(512)
		NOT NULL,
  CONSTRAINT entity_external_id_code_type_u
    UNIQUE (code, entity_type),
  CONSTRAINT entity_external_id_codestr_type_u
    UNIQUE (code_str, entity_type)
);


/* Insert entity_external_id */


category:pre;
CREATE TABLE entity_external_id
(
  entity_id	NUMERIC(12,0),
  entity_type	NUMERIC(6,0),
  id_type	NUMERIC(6,0)
                NOT NULL,
  source_system	NUMERIC(6,0)
                NOT NULL
		CONSTRAINT entity_external_id_source_sys
		  REFERENCES authoritative_system_code(code),
  external_id	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT entity_external_id_pk
    PRIMARY KEY (entity_id, id_type, source_system),
  CONSTRAINT entity_external_id_u
    UNIQUE (id_type, source_system, external_id),
  CONSTRAINT entity_external_id_entity_id FOREIGN KEY (entity_id, entity_type)
    REFERENCES entity_info(entity_id, entity_type),
  CONSTRAINT entity_spread_spread FOREIGN KEY (id_type, entity_type)
    REFERENCES entity_external_id_code(code, entity_type)
);

category:pre;
CREATE INDEX entity_external_id_ext_id ON entity_external_id(external_id);

category:post;
DROP TABLE person_external_id;
category:post;
DROP TABLE person_external_id_code;

/* arch-tag: c3e14dc4-0751-467f-b340-c1c7cffad890
   (do not change this comment) */
