/* encoding: utf-8
 *
 * Copyright 2013-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.gpg
 */
category:metainfo;
name=gpg;

category:metainfo;
version=1.0;

category:drop;
DROP TABLE entity_gpg_data;

category:drop;
DROP SEQUENCE gpg_message_id_seq;

category:main;
CREATE SEQUENCE gpg_message_id_seq;

category:main;
CREATE TABLE entity_gpg_data
(
  message_id
    NUMERIC(12,0)
    CONSTRAINT entity_gpg_message_pk PRIMARY KEY,

  entity_id
    NUMERIC(12,0)
    REFERENCES entity_info(entity_id),

  recipient
    CHAR VARYING(40)
    NOT NULL,

  tag
    CHAR VARYING(60)
    NOT NULL,

  created
    TIMESTAMP
    DEFAULT [:now]
    NOT NULL,

  message
    TEXT
    NOT NULL
);

category:main;
CREATE INDEX entity_gpg_data_entity_idx ON entity_gpg_data(entity_id);

category:main;
CREATE INDEX entity_gpg_data_recipient_idx on entity_gpg_data(recipient);

category:main;
CREATE INDEX entity_gpg_data_entity_recipient_tag_idx on entity_gpg_data(entity_id, recipient, tag);
