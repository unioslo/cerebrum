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
 *
 *
 * Tables used by Cerebrum.modules.task_queue
 *
 * The event queue is used for delayed processing of changes in
 * Cerebrum.  It was developed mainly as temporary storage of source system ids
 * to look up and import from the hr-system (Cerebrum.modules.hr_import).
 *
 * Each row in the task_queue table is a single event that should be processed
 * by some queue-subsystem in Cerebrum.
 *
 * Note: This database module uses postgres-only features.
 */
category:metainfo;
name=task_queue;

category:metainfo;
version=1.1;


/* TABLE task_queue
 *
 * queue
 *   identifies a single queue
 *
 * key
 *   a unique item identifier within a queue.
 *
 * sub
 *   sub queue/subject. Usage is optional, and depends on queue.  By default,
 *   this column is an empty string, and can be ignored.
 *
 * iat
 *   issued at timestamp -- when the item was added to the queue
 *
 * nbf
 *   not before timestamp -- when the item should be processed
 *
 * attempts
 *   counter -- how many times this item has been processed
 *
 * reason
 *   Optional human readable description of *why* the event was queued (for
 *   debug purposes).
 *
 * payload
 *   Optional JSON encoded item data - content depends on the queue
 */
category:main;
CREATE TABLE IF NOT EXISTS task_queue
(
  queue
    TEXT
    NOT NULL
    CONSTRAINT task_queue_queue_chk
      CHECK (queue != ''),

  key
    TEXT
    NOT NULL
    CONSTRAINT task_queue_key_chk
      CHECK (key != ''),

  sub
    TEXT
    NOT NULL
    DEFAULT '',

  iat
    TIMESTAMP WITH TIME ZONE
    NOT NULL
    DEFAULT now(),

  nbf
    TIMESTAMP WITH TIME ZONE
    NOT NULL
    DEFAULT now(),

  attempts
    INT
    NOT NULL
    DEFAULT 0,

  reason
    TEXT
    NULL,

  payload
    JSONB
    NULL,

  CONSTRAINT task_queue_pk PRIMARY KEY (queue, sub, key)
);

category:main;
CREATE INDEX IF NOT EXISTS task_queue_nbf_idx ON task_queue(nbf);

category:main;
CREATE INDEX IF NOT EXISTS task_queue_iat_idx ON task_queue(iat);

category:drop;
DROP TABLE IF EXISTS task_queue;

