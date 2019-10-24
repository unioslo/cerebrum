/*
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
 */

category:pre;
CREATE TABLE group_type_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT group_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(32)
    NOT NULL
    CONSTRAINT group_type_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);

category:pre;
ALTER TABLE group_info
  ADD COLUMN group_type
    NUMERIC(6,0)
    DEFAULT NULL
    CONSTRAINT group_info_type
      REFERENCES group_type_code(code);

/**
 * Migration needs to:
 * 1. Insert an initial, default group_type_code
 * 2. Update all groups with this default value, so we can add a NOT NULL
 *    constraint.
 */

category:post;
ALTER TABLE group_info
  ALTER COLUMN group_type SET NOT NULL;
