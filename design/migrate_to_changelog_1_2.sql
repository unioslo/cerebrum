/*
 * Copyright 2007 University of Oslo, Norway
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

/* SQL script for migrating from changelog 1.1 to 1.2 */

/* Expand change_log.change_params column.  4000 is the maximum Oracle
   accepts. */
category:pre;
ALTER TABLE change_log ADD COLUMN change_params_new CHAR VARYING(4000);
category:pre;
UPDATE change_log SET change_params_new = change_params;
category:pre;
ALTER TABLE change_log DROP COLUMN change_params;
category:pre;
ALTER TABLE change_log RENAME COLUMN change_params_new TO change_params;

/* Expand change_log.change_program.  16 was a bit short. */
category:pre;
ALTER TABLE change_log ADD COLUMN change_program_new CHAR VARYING(64);
category:pre;
UPDATE change_log SET change_program_new = change_program;
category:pre;
ALTER TABLE change_log DROP COLUMN change_program;
category:pre;
ALTER TABLE change_log RENAME COLUMN change_program_new TO change_program;

/* Drop change_log.description -- it's unused */
category:pre;
ALTER TABLE change_log DROP COLUMN description;

/* Expand code values, first change_type.category */
category:pre;
ALTER TABLE change_type ADD COLUMN category_new CHAR VARYING(32);
category:pre;
UPDATE change_type SET category_new = category;
category:pre;
ALTER TABLE change_type ALTER COLUMN category_new SET NOT NULL;
category:pre;
ALTER TABLE change_type DROP COLUMN category;
category:pre;
ALTER TABLE change_type RENAME COLUMN category_new TO category;

/* Now change_type.type */
category:pre;
ALTER TABLE change_type ADD COLUMN type_new CHAR VARYING(32);
category:pre;
UPDATE change_type SET type_new = type;
category:pre;
ALTER TABLE change_type ALTER COLUMN type_new SET NOT NULL;
category:pre;
ALTER TABLE change_type DROP COLUMN type;
category:pre;
ALTER TABLE change_type RENAME COLUMN type_new TO type;

/* There were no contraints previously */
category:pre;
ALTER TABLE change_type ALTER COLUMN category SET NOT NULL;
category:pre;
ALTER TABLE change_type ALTER COLUMN type SET NOT NULL;
category:pre;
ALTER TABLE change_type ADD CONSTRAINT change_type_u UNIQUE (category, type);

