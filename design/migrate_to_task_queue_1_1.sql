/* encoding: utf-8
 *
 * Copyright 2021 University of Oslo, Norway
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

/**
 * Add a sub column, and add to primary key
 */
category:pre;
ALTER TABLE task_queue DROP CONSTRAINT task_queue_pk;

category:pre;
ALTER TABLE task_queue ADD sub TEXT NOT NULL DEFAULT '';

category:pre;
ALTER TABLE task_queue ADD CONSTRAINT task_queue_pk PRIMARY KEY (queue, sub, key);

/**
 * Add indexes on nbf and iat, as they are involved in sorting and queries.
 */
category:pre;
CREATE INDEX task_queue_nbf_idx ON task_queue(nbf);

category:pre;
CREATE INDEX task_queue_iat_idx ON task_queue(iat);
