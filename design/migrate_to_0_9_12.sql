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

/* SQL script for migrating a 0.9.11 database to 0.9.12 */

/* Drop the column description from table person_affiliation_source.
   The column is not used in the Cerebrum API 
*/

category:pre;
ALTER TABLE entity_address ADD COLUMN postal_number_new  CHAR VARYING(32);
category:pre;
UPDATE entity_address SET postal_number_new = postal_number;
category:pre;
ALTER TABLE entity_address DROP COLUMN postal_number;
category:pre;
ALTER TABLE entity_address RENAME COLUMN postal_number_new TO postal_number;

