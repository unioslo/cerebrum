/* encoding: utf-8
 *
 * Copyright 2012-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.ad2.Entity
 *
 * Module `entity_ad_attributes' -- attach AD-attributes to entities.
 *
 * This module allows local mixins to administrate AD-attributes for entities
 * to be synchronized with Active Directory.
 */
category:metainfo;
name=ad_attributes;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE ad_attribute;

category:drop;
DROP TABLE ad_attribute_code;


/*
 * ad_attribute_codes
 *
 * Code table that defines all the attributes we could administrate for AD. Also
 * defines if the attribute is multivalued or not, as this defines the number of
 * elements an attribute could have.
 */
category:code;
CREATE TABLE ad_attribute_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT ad_attribute_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(128)
    NOT NULL
    CONSTRAINT ad_attribute_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL,

  multivalued
    BOOLEAN
    NOT NULL
    DEFAULT FALSE
);


/*
 * ad_attribute
 *
 * Where we store the attributes for different entities.
 *
 *
 */
category:main;
CREATE TABLE ad_attribute
(
  /* The entity the attribute is registered for: */
  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT ad_attribute_entity_id
      REFERENCES entity_info(entity_id),

  /* TODO: do we need entity_type? */

  /* The type of attribute: */
  attr_code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT ad_attribute_attr_code
      REFERENCES ad_attribute_code(code),

  /* What spread the attribute is related to: */
  spread_code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT ad_attribute_spread_code
      REFERENCES spread_code(code),

  /* If multivalued, to separate each element: */
  subattr_id
    NUMERIC(6,0),
    /* TODO: how to automatically create a sequence for this? */

  /* The value of the attribute: */
  value
    CHAR VARYING(1024)
    NOT NULL,

  CONSTRAINT ad_attribute_pk
    PRIMARY KEY (entity_id, attr_code, spread_code, subattr_id)
    /* TODO: foreign keys too? */
);
