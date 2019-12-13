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
 * Tables used by Cerebrum.modules.legacy_users
 *
 * This module is based on a table from cerebrum @ uit:
 *
 *            Table "public.legacy_users"
 *    Column   |          Type          | Modifiers
 *  -----------+------------------------+-----------
 *   user_name | character varying(12)  | not null
 *   ssn       | character varying(256) |
 *   source    | character varying(12)  | not null
 *   type      | character varying(12)  | not null
 *   comment   | character varying(255) |
 *   name      | character varying(60)  |
 *  Indexes:
 *      "legacy_user_name" PRIMARY KEY, btree (user_name)
 */
category:metainfo;
name=legacy_users;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE legacy_users;


/**
 * legacy_users
 *
 * user_name
 *   A locked/reserved/previously used username.
 * ssn
 *   Norwegian National ID of the person who owns/owned this username.
 * source
 *   Where this username comes from.
 * type
 *   TODO: ?
 * comment
 *   A human readable comment on why this entry exists.
 * name
 *   TODO: ?
**/
category:main;
CREATE TABLE legacy_users
(
  user_name
    CHAR VARYING(12)
    NOT NULL,

  ssn
    CHAR VARYING(256),

  source
    CHAR VARYING(12)
    NOT NULL,

  type
    CHAR VARYING(12)
    NOT NULL,

  comment
    CHAR VARYING(255),

  name
    CHAR VARYING(60),

  CONSTRAINT legacy_user_name PRIMARY KEY (user_name)
);
