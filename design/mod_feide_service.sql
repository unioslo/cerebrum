/* encoding: utf-8
 *
 * Copyright 2016-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.feide
 */
category:metainfo;
name=feide_service;

category:metainfo;
version=1.1;


category:drop;
DROP TABLE feide_service_info;

category:drop;
DROP TABLE feide_service_authn_level;


category:main;
CREATE TABLE feide_service_info
(
  service_id
    NUMERIC(12,0)
    CONSTRAINT feide_service_info_pk PRIMARY KEY,

  feide_id
    VARCHAR(128,0)
    NOT NULL
    CONSTRAINT feide_service_info_feide_id_unique UNIQUE,

  name
    VARCHAR(128)
    NOT NULL
    CONSTRAINT feide_service_info_name_unique UNIQUE
);


category:main;
CREATE TABLE feide_service_authn_level
(
  service_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_service_authn_level_service_relationship
      REFERENCES feide_service_info(service_id),

  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_service_authn_level_entity_relationship
      REFERENCES entity_info(entity_id),

  level
    NUMERIC(1,0)
    NOT NULL
);
