/*
 * Copyright 2015 University of Oslo, Norway
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

category:metainfo;
name=event-publisher;
category:metainfo;
version=1.0;



category:drop;
drop TABLE unpublished_events;

category:drop;
drop SEQUENCE eventpublisher_seq;

category:code;
CREATE SEQUENCE eventpublisher_seq;

category:main;
CREATE TABLE unpublished_events
(
  tstamp          TIMESTAMP
                  DEFAULT [:now]
                  NOT NULL,
  eventid         NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT event_id_pk PRIMARY KEY,
  message         TEXT
);

category:main;
CREATE INDEX eventpubl_id_by_idx ON unpublished_events(eventid);

