/* encoding: utf-8
 *
 * Copyright 2017-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.event_publisher
 */
category:metainfo;
name=events;

category:metainfo;
version=1.0;


/* event_id sequence */
category:main;
CREATE SEQUENCE events_seq;


/* event table */
category:main;
CREATE TABLE events
(
  /* A unique ID for this event */
  event_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT events_event_id_pk PRIMARY KEY,

  /* The type of event. This should be a SCIM-verb */
  event_type
    VARCHAR(64)
    NOT NULL,

  /* The subject entity_id. Not used for processing, but useful if we need to
   * look up unprocessed events for some reason.
   * TODO: Move all subject data to event_data? */
  subject_id
    NUMERIC(12,0)
    NOT NULL,

  /* The subject entity_type (code_str) */
  subject_type
    VARCHAR(64)
    NOT NULL,

  /* The subject identifier (e.g. entity_name, sko, entity_id) */
  subject_ident
    VARCHAR(128)
    NOT NULL,

  /* Event creation time */
  timestamp
    TIMESTAMP
    DEFAULT [:now]
    NOT NULL,

  /* Event scheduling time */
  /* TODO: DEFAULT [:now] NOT NULL ? */
  schedule
    TIMESTAMP,

  /* Event lock time, indicates that a worker has started processing
   * the event */
  taken_time
    TIMESTAMP,

  /* Number of times the event has been locked for processing. */
  failed
    NUMERIC(12,0)
    DEFAULT 0,

  /* Additional (JSON-serialized) event data.
   * Contains info about:
   *  - audience (list of spread code_str)
   *  - object references (other affected entities)
   *  - affected attributes
   * TODO: Change this to a 'json' or 'jsonb' field.
   */
  event_data
    TEXT
);


/* trigger function
 * issues a NOTIFY event_publisher with the event_id of new rows from the events
 * table */
category:main;
CREATE OR REPLACE FUNCTION events_publish() RETURNS TRIGGER AS '
  DECLARE
    r RECORD;
  BEGIN
    PERFORM pg_notify($$event_publisher$$, CAST(NEW.event_id AS text));
    RETURN NULL;
  END;
' LANGUAGE plpgsql;


/* insert trigger on events */
category:main;
CREATE TRIGGER events_publish_trigger
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE PROCEDURE events_publish();


category:drop;
DROP SEQUENCE events_seq;

category:drop;
DROP TRIGGER events_publish_trigger ON events;

category:drop;
DROP TABLE events;

category:drop;
DROP FUNCTION events_publish();
