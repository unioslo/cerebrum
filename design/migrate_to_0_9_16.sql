/*
 * Copyright 2011 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.15 database to 0.9.16 */

/* 
 * This migration job is part of the entity-with-name-with-language upgrade. 
 * 
 * **FAT ASS WARNING**
 * 
 * This is what happens to the database after this migration script has been
 * run:
 *
 * - ou_info loses all of its *name columns (they'd have to be reimported)
 * - ou_name_language is dropped permanently (all of its content, if any, is 
 *   lost)
 * - the API is supposed to commit OU name data to entity_language_name. 
 */



category:pre;
CREATE TABLE entity_name_code
(
	code		NUMERIC(6, 0)
			CONSTRAINT entity_name_code_pk PRIMARY KEY,
        code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT entity_name_codestr_u UNIQUE,
        description	CHAR VARYING(512)
			NOT NULL
);



category:pre;
CREATE TABLE entity_language_name
(
	entity_id	NUMERIC(12, 0)
			CONSTRAINT entity_lang_name_id
			  REFERENCES entity_info(entity_id),
        name_variant	NUMERIC(6, 0)
			CONSTRAINT entity_lang_name_code_fk
			  REFERENCES entity_name_code(code),
        name_language   NUMERIC(6, 0)
			CONSTRAINT entity_lang_name_lang_fk
			  REFERENCES language_code(code),
        name 		CHAR VARYING(512)
			NOT NULL,

        CONSTRAINT entity_lang_name_pk
	  PRIMARY KEY (entity_id, name_variant, name_language)
);

category:pre;
CREATE INDEX eln_entity_id_index ON entity_language_name(entity_id);
category:pre;
CREATE INDEX eln_name_variant_index ON entity_language_name(name_variant);
category:pre;
CREATE INDEX eln_name_language_index ON entity_language_name(name_language);



/*
 * drop ou_name_language - entity_language_name has taken over its 
 * functionality.
 */
category:pre;
DROP TABLE ou_name_language;



/* 
 * drop the name columns from ou_info. They are migrating to
 * entity_language_name 
 */
category:post;
ALTER TABLE ou_info
DROP COLUMN name ;

category:post;
ALTER TABLE ou_info
DROP COLUMN acronym ;

category:post;
ALTER TABLE ou_info
DROP COLUMN short_name ;

category:post;
ALTER TABLE ou_info
DROP COLUMN display_name ;

category:post;
ALTER TABLE ou_info
DROP COLUMN sort_name ;
