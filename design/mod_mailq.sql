/* encoding: utf-8
 *
 * Copyright 2003-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.mailq
 *
 * This module is based on a table from cerebrum @ uit:
 *
 *                   Table "public.mailq"
 *     Column    |            Type             | Modifiers
 *  -------------+-----------------------------+-----------
 *   entity_id   | numeric(12,0)               | not null
 *   template    | character varying(50)       | not null
 *   parameters  | text                        | not null
 *   scheduled   | timestamp without time zone | not null
 *   status      | numeric(1,0)                | not null
 *   status_time | timestamp without time zone | not null
 *  Indexes:
 *      "mailq_pkey" PRIMARY KEY, btree (entity_id, template)
 *  Foreign-key constraints:
 *      "$1" FOREIGN KEY (entity_id) REFERENCES entity_info(entity_id)
 *
 * Yes, the constraint is literally named "$1". When migrating the UiT database,
 * we'll have to manually
 *    ALTER TABLE mailq RENAME CONSTRAINT "$1" TO mailq_fkey;
 */
category:metainfo;
name=mailq;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE mailq;


/**
 * mailq
 *
 * Queue of email templates to send out to entities.
 *
 * entity_id
 *   The entity to notify.
 * template
 *   The notification template to use.
 * parameters
 *   Notification settings for the template.
 * scheduled
 *   When notification should be sent.
 * status
 *   0 if pending, 1 if failed - entries that are processed successfully are
 *   removed.
 * status_time:
 *   When the status was last altered
**/
category:main;
CREATE TABLE mailq
(
  entity_id
    NUMERIC(12,0)
    NOT NULL,

  template
    CHAR VARYING(50)
    NOT NULL,

  parameters
    TEXT
    NOT NULL,

  scheduled
    TIMESTAMP WITHOUT TIME ZONE
    NOT NULL,

  status
    NUMERIC(1,0)
    NOT NULL,

  status_time
    TIMESTAMP WITHOUT TIME ZONE
    NOT NULL,

  CONSTRAINT mailq_pkey PRIMARY KEY (entity_id, template),
  CONSTRAINT mailq_fkey FOREIGN KEY (entity_id) REFERENCES entity_info(entity_id)
);
