/*
 * Copyright 2006 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.7 database to 0.9.8 */


/* Move host_info.name into entity_name */
category:post;
INSERT INTO entity_name (entity_id, value_domain, entity_name)
  SELECT host_id AS entity_id,
         [:get_constant name=host_namespace] AS volume_domain,
         name AS entity_name
    FROM host_info;
category:post;
ALTER TABLE host_info DROP COLUMN name;

/* arch-tag: 3a8df4c6-ba40-11da-98aa-ecfb74a7c630
   (do not change this comment) */
