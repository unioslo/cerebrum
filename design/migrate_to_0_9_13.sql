/*
 * Copyright 2008 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.12 database to 0.9.13 */

/* Drop the 'operation' column from group_member, since it has not been used
   in client code, ever. */

category:pre;
ALTER TABLE group_member DROP CONSTRAINT group_member_pk;
category:pre;
ALTER TABLE group_member DROP CONSTRAINT group_member_operation;
category:pre;
ALTER TABLE group_member DROP COLUMN operation;

category:pre;
ALTER TABLE group_member ADD CONSTRAINT group_member_pk
      PRIMARY KEY (group_id, member_id);

