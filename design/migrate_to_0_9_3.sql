/*
 * Copyright 2004 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.2 database to 0.9.3
*/
category:pre;
ALTER TABLE auth_op_target ADD COLUMN attr CHAR VARYING(50);

category:post;
ALTER TABLE auth_op_target DROP COLUMN has_attr;
category:post;
DROP TABLE auth_op_target_attrs;

/* arch-tag: f4411d8a-a413-4bcc-b26e-2caaff887540
   (do not change this comment) */
