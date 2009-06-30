/*
 * Copyright 2009 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.13 database to 0.9.14 */

/* Fix typo in constraint name */

category:pre;
ALTER TABLE entity_external_id DROP CONSTRAINT entity_spread_spread;

category:post;
ALTER TABLE entity_external_id ADD CONSTRAINT entity_external_id_id_type 
      FOREIGN KEY (id_type, entity_type) 
      REFERENCES entity_external_id_code(code, entity_type);
