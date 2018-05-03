/*
 * Copyright 2013 University of Oslo, Norway
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
name=eventlog;
category:metainfo;
version=1.1;


category:drop;
DROP TRIGGER event_notify_trigger ON event_log;

category:drop;
DROP FUNCTION send_event_notify();

category:drop;
DROP TABLE event_to_target;

category:drop;
DROP TABLE event_log;

category:drop;
DROP TABLE target_system_code;

category:drop;
DROP SEQUENCE event_log_seq;

category:code;
CREATE SEQUENCE event_log_seq;

category:code;
CREATE TABLE target_system_code
(
    code            NUMERIC(6,0)
                    NOT NULL
                    CONSTRAINT target_system_code_pk PRIMARY KEY,
    code_str        CHAR VARYING(16)
                    NOT NULL
                    CONSTRAINT target_system_code_str UNIQUE,
    description     CHAR VARYING(512)
                    NOT NULL
);

category:code;
CREATE TABLE event_to_target
(
    target_system   NUMERIC(6,0)
                    REFERENCES target_system_code(code),
    event_type      NUMERIC(6,0)
                    REFERENCES change_type(change_type_id),
    CONSTRAINT target_system_event_type_u
        UNIQUE (target_system, event_type)
);

category:main;
CREATE TABLE event_log
(
    tstamp          TIMESTAMP
                    DEFAULT [:now]
                    NOT NULL,
    event_id        NUMERIC(12,0)
                    NOT NULL
                    CONSTRAINT event_id_pk PRIMARY KEY,
    event_type      NUMERIC(6,0)
                    REFERENCES change_type(change_type_id),
    target_system   NUMERIC(12,0)
                    REFERENCES target_system_code(code),
    subject_entity  NUMERIC(12,0),
    dest_entity     NUMERIC(12,0),
    taken_time      TIMESTAMP,
    failed          NUMERIC(12,0)
                    DEFAULT 0,
    change_params   CHAR VARYING(4000)
);

/*
We can't use dollar quoting in the function block, since Plex goes bananas
when it encounters dollars :( If Plex starts to behave, change this!
 */
category:main;
CREATE OR REPLACE FUNCTION send_event_notify() RETURNS TRIGGER AS '
  DECLARE
    r RECORD;
  BEGIN
    SELECT * INTO r FROM target_system_code WHERE code = NEW.target_system;
    PERFORM pg_notify(r.code_str, CAST(NEW.event_id AS text));
    RETURN NULL;
  END;
' LANGUAGE plpgsql;

category:main;
CREATE TRIGGER event_notify_trigger
    AFTER INSERT ON event_log
    FOR EACH ROW
    EXECUTE PROCEDURE send_event_notify();

