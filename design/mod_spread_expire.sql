/* encoding: utf-8
 *
 * Copyright 2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.spread_expire
 *
 * This module is based on tables from cerebrum @ uit:
 *
 *
 *        Table "public.spread_expire"
 *     Column    |     Type      | Modifiers
 *  -------------+---------------+-----------
 *   entity_id   | numeric(12,0) | not null
 *   spread      | numeric(6,0)  | not null
 *   expire_date | date          | not null
 *
 */
category:metainfo;
name=spread_expire;

category:metainfo;
version=1.1;


category:drop;
DROP TABLE spread_expire;


/**
 * spread_expire
 *
 * A list of expire dates for entity_spread.
 *
 * entity_id
 *   The entity with a spread expire date.
 * spread
 *   The spread with an expire date.
 * expire_date
 *   Expire date for the (entity_id, spread) combo.
**/
category:main;
CREATE TABLE spread_expire
(
  entity_id
    NUMERIC(12,0)
    NOT NULL,

  spread
    NUMERIC(6,0)
    NOT NULL,

  expire_date
    DATE
    NOT NULL
);
