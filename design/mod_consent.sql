/* encoding: utf-8
 *
 * Copyright 2015-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.consent
 */
category:metainfo;
name=consent;

category:metainfo;
version=1.0;


category:drop;
drop TABLE entity_consent;

category:drop;
drop TABLE entity_consent_code;

category:drop;
drop TABLE consent_type_code;


category:code;
CREATE TABLE consent_type_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT consent_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT consent_type_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE entity_consent_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT entity_consent_code_pk PRIMARY KEY,

  entity_type
    NUMERIC(6,0)
    CONSTRAINT entity_consent_entity_type
    REFERENCES entity_type_code(code)
    NOT NULL,

  consent_type
    NUMERIC(6,0)
    CONSTRAINT entity_consent_consent_type
      REFERENCES consent_type_code(code)
    NOT NULL,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT entity_consent_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:main;
CREATE TABLE entity_consent
(
  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT entity_consent_entity_id_fk
      REFERENCES entity_info(entity_id),

  consent_code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT entity_consent_consent_code_fk
      REFERENCES entity_consent_code(code),

  time_set
    TIMESTAMP
    NOT NULL
    DEFAULT [:now],

  expiry
    TIMESTAMP
    NULL
    DEFAULT NULL,

  description
    CHAR VARYING(512),

  CONSTRAINT entity_consent_pk PRIMARY KEY (entity_id, consent_code)
);
