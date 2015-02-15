/*
 * Copyright 2015 University of Oslo, Norway
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

/* SQL script for migrating a mod_email 1.4 to 1.5 */
/* Creates table for local-delivery flag */

category:pre;
CREATE TABLE email_local_delivery
(
  target_id	NUMERIC(12,0) UNIQUE
		CONSTRAINT email_forward_target_id
		  REFERENCES email_target(target_id),
  local_delivery BOOLEAN
        NOT NULL
);
