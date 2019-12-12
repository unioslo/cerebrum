/* encoding: utf-8
 *
 * Copyright 2005-2019 University of Oslo, Norway
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
 *
 *
 * Tables used by Cerebrum.modules.EntityTrait
 *
 * Module `entity_trait' -- attach auxilliary information to entities.
 *
 * This module allows scripts or local mixins to attach information to
 * entities so that state can be kept across invocations.
 */
category:metainfo;
name=entity_trait;

category:metainfo;
version=1.1;

category:drop;
DROP TABLE entity_trait;

category:drop;
DROP TABLE entity_trait_code;


/*  entity_trait_code
 *
 * A typical code table for use in entity_trait, with an extra column
 * entity_type to limit the semantics of a code value.
 */
category:code;
CREATE TABLE entity_trait_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT entity_trait_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT entity_trait_codestr_u UNIQUE,

  entity_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT entity_trait_code_entity_type
      REFERENCES entity_type_code(code),

  description
    CHAR VARYING(512)
    NOT NULL,

  CONSTRAINT entity_trait_code_entity_type_u
    UNIQUE (code, entity_type)
);


/*  entity_trait
 *
 * entity_type
 * entity_id
 *     Identifies the entity which has the trait
 * code
 *     A code value specifying type of information
 *
 * The rest of the columns are optional, depending on the code.
 * Unfortunately, we can't enforce that the relevant columns are
 * non-NULL for each code, we must trust the Python code.
 *
 * target_id
 *     An entity
 * date
 *     A timestamp
 * numval
 *     An integer value
 * strval
 *     Free-form text
 */
category:main;
CREATE TABLE entity_trait
(
  entity_id
    NUMERIC(12,0)
    NOT NULL,

  entity_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT entity_trait_entity_type
      REFERENCES entity_type_code(code),

  code
    NUMERIC(6,0)
    NOT NULL,

  target_id
    NUMERIC(12,0)
    CONSTRAINT entity_trait_target_id
      REFERENCES entity_info(entity_id),

  date
    TIMESTAMP,

  numval
    NUMERIC(12,0),

  strval
    TEXT,

  CONSTRAINT entity_trait_pk PRIMARY KEY (entity_id, code),
  CONSTRAINT entity_trait_entity_id FOREIGN KEY (entity_id, entity_type)
    REFERENCES entity_info(entity_id, entity_type),
  CONSTRAINT entity_trait_code FOREIGN KEY (code, entity_type)
    REFERENCES entity_trait_code(code, entity_type)
);
