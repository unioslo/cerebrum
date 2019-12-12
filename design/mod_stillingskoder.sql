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
 * Tables used by Cerebrum.modules.stillingskoder
 *
 * This module is based on a table from cerebrum @ uit:
 *
 *           Table "public.person_stillingskoder"
 *       Column      |          Type          | Modifiers
 *  -----------------+------------------------+-----------
 *   stillingskode   | numeric(6,0)           | not null
 *   stillingstittel | character varying(256) | not null
 *   stillingstype   | character varying(256) | not null
 *  Indexes:
 *      "person_stillingskode" PRIMARY KEY, btree (stillingskode)
 */
category:metainfo;
name=stillingskoder;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE person_stillingskoder;


/**
 * person_stillingskoder
 *
 * stillingskode
 *   Employment code
 * stillingstittel
 *   Employment title
 * stillingstype
 *   Employment category
**/
category:main;
CREATE TABLE person_stillingskoder
(
  stillingskode
    NUMERIC(6,0)
    NOT NULL,

  stillingstittel
    CHAR VARYING(256)
    NOT NULL,

  stillingstype
    CHAR VARYING(256)
    NOT NULL,

  CONSTRAINT person_stillingskode PRIMARY KEY (stillingskode)
);
