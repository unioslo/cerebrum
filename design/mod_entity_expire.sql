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
 * Tables used by Cerebrum.modules.entity_expire
 *
 * Module 'EntityExpire' -- attach expire date to entities.
 *
 * This Module ads expire_date to any Entity. It will enable basic
 * functionality to administer the new attribute, for example
 * set_expire_date, remove_expire_date, is_expired, etc.
 * Read more in module API documentation / docstrings.
 */
category:metainfo;
name=entity_expire;

category:metainfo;
version=1.0;

category:drop;
DROP TABLE entity_expire;


/*  entity_expire
 *
 * entity_id
 * expire_date - Expire date of entity.
 */
category:main;
CREATE TABLE entity_expire
(
  entity_id
    NUMERIC(12,0)
    NOT NULL,

  expire_date
    DATE
    DEFAULT [:now]
    NOT NULL,

  CONSTRAINT entity_expire_pk
    PRIMARY KEY (entity_id),

  CONSTRAINT entity_expire_entity_id_fk
    FOREIGN KEY (entity_id)
    REFERENCES entity_info(entity_id)
);
