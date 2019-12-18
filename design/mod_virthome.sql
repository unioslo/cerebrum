/* encoding: utf-8
 *
 * Copyright 2009-2019 University of Oslo, Norway
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
 *
 *
 * Tables used by Cerebrum.modules.virthome
 *
 * Depends on mod_changelog
 */
category:metainfo;
name=virthome;

category:metainfo;
version=1.0;


category:main;
CREATE TABLE pending_change_log
(
  confirmation_key
    CHAR VARYING(256)
    NOT NULL,

  change_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT pending_change_log_cl_exists
      REFERENCES change_log(change_id),

  CONSTRAINT pending_change_log_primary_key
    PRIMARY KEY(change_id),

  CONSTRAINT pending_change_log_conf_unique
    UNIQUE(change_id)
);

category:main;
CREATE INDEX pending_change_log_conf_idx
  ON pending_change_log(confirmation_key);


category:drop;
DROP TABLE pending_change_log;
