/*
 * Copyright 2016 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.18 database to 0.9.19 */

/* Add new column which defaults to NULL */
category:pre;
ALTER TABLE entity_info ADD COLUMN
    created_at TIMESTAMP NULL;

/* Migrate should now have filled with values */

/* Use NOW() as created_at for all new entities. */
category:post;
ALTER TABLE entity_info ALTER COLUMN
    created_at SET DEFAULT [:now];

/* Drop the redundant columns */
category:post;
ALTER TABLE account_info DROP COLUMN create_date;
category:post;
ALTER TABLE group_info DROP COLUMN create_date;