/*
 * Copyright 2002, 2003 University of Oslo, Norway
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
 */

category:metainfo;
name=password_history;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE password_history;
category:main;
CREATE TABLE password_history
(
  entity_id     NUMERIC(12,0)
                CONSTRAINT password_history_entity_id 
                  REFERENCES entity_info(entity_id),
  md5base64     CHAR VARYING(22)
                NOT NULL,
  set_at        TIMESTAMP
                DEFAULT [:now]
);
category:main;
CREATE INDEX password_hist_ety_idx ON password_history(entity_id);

/* arch-tag: ccd17681-96b9-4d9a-8d1f-412c313f9202
   (do not change this comment) */
