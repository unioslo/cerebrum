/*
 * Copyright 2005 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.6 database to 0.9.7 */


/* Change value domain for field deceases in person_info. Rename field to deceased_date*/
category:pre;
ALTER TABLE person_info ADD COLUMN
  deceased_date    DATE;
category:pre;
ALTER TABLE person_info ADD CONSTRAINT deceased_date_chk
  CHECK (deceased_date <= [:now]);
category:post;
ALTER TABLE person_info DROP COLUMN deceased;

/* arch-tag: 15840f8c-35ff-11da-982a-e6fabc13acbf
   (do not change this comment) */
