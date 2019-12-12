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
 * Tables used by Cerebrum.modules.virtualgroup.Group
 */
category:metainfo;
name=virtual_group;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE virtual_group_info;

category:drop;
DROP TABLE virtual_group_type_code;


category:code;
CREATE TABLE virtual_group_type_code
(
  code
    NUMERIC(6,0)
    PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  virtual_group_info
 *
 * As virtual group, but an extra virtual_group_type
 *
 */
category:main;
CREATE TABLE virtual_group_info
(
  group_id
    NUMERIC(12,0)
    CONSTRAINT virtual_group_info_pk PRIMARY KEY,

  virtual_group_type
    NUMERIC(6,0)
    NOT NULL
    REFERENCES virtual_group_type_code
);

category:main/Oracle;
GRANT SELECT ON virtual_group_info TO read_group;

category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON virtual_group_info TO change_group;
