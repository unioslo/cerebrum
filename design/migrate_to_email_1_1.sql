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

/* SQL script for migrating a mod_email 1.0 to 1.1 */


category:pre;
ALTER TABLE email_target ADD server_id NUMERIC(12,0)
        CONSTRAINT email_target_server_server_id
                REFERENCES email_server(server_id);

category:pre;
ALTER TABLE email_target ADD CONSTRAINT email_target_entity_server_u
        UNIQUE (entity_id, server_id);

category:pre;
ALTER TABLE email_target DROP CONSTRAINT email_target_entity_u;

category:pre;
UPDATE email_target SET server_id = ets.server_id
  FROM email_target_server ets WHERE email_target.target_id = ets.target_id;

category:pre;
DROP TABLE email_server_target;
