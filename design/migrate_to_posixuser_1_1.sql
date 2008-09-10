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

/* SQL script for migrating posix_user to schema version in conjunction with
 * version 0.9.13 of core_tables.sql */

/* group_member.operation is no longer there */

category:pre;
ALTER TABLE posix_user DROP CONSTRAINT posix_user_in_primary_group;

category:pre;
ALTER TABLE posix_user DROP COLUMN pg_member_op;

category:post;
ALTER TABLE posix_user ADD CONSTRAINT posix_user_in_primary_group
      FOREIGN KEY (gid, account_id)
      REFERENCES group_member(group_id, member_id);
