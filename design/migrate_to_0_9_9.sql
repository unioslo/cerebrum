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

/* SQL script for migrating a 0.9.8 database to 0.9.9 */

/* Temporarely add an index that speeds up the migration.  Since the
   index is not normally needed, we remove it afterwards.  */
category:pre;
CREATE INDEX tmp_account_home_homedir_idx on account_home(homedir_id);

/* Stricter constraint on the account_home table */
category:post;
ALTER TABLE account_home ADD CONSTRAINT ac_home_spread 
    FOREIGN KEY (account_id, spread) REFERENCES 
        entity_spread(entity_id, spread);

category:post;
DROP INDEX tmp_account_home_homedir_idx;
