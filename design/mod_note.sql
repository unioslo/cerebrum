/*
 * Copyright 2004 University of Oslo, Norway
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

category:drop;
drop TABLE note;

category:code;
CREATE SEQUENCE note_seq;

category:main;
CREATE TABLE note
(
  note_id       NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_id_pk PRIMARY KEY,
                  DEFAULT
  create_date   TIMESTAMP
                  DEFAULT [:now]
                  NOT NULL,
  creator_id    NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_creator_id
                    REFERENCES account_info(account_id),
  entity_id     NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_entity_id
                    REFERENCES entity_info(entity_id),
  subject       CHAR VARYING(70),
  description   CHAR VARYING(1024)
);

/* arch-tag: 285dc8de-aa86-4720-be3e-33b8fae0a84c
   (do not change this comment) */
