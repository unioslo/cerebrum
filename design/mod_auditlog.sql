/*
 * Copyright 2018 University of Oslo, Norway
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
name=auditlog;

category:metainfo;
version=1.0;

category:drop;
drop TABLE audit_log;

category:drop;
drop SEQUENCE audit_log_seq;

category:code;
CREATE SEQUENCE audit_log_seq;

category:main;
CREATE TABLE audit_log
(
  /* Timestamp with timezone */
  timestamp       TIMESTAMP
                  WITH TIME ZONE
                  NOT NULL
                  DEFAULT [:now],

  /* A unique ID of this change record */
  record_id       NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT record_idx PRIMARY KEY,

  /* Changelog constant for this change */
  change_type     NUMERIC(6,0)
                  NOT NULL
                  REFERENCES change_type(change_type_id),

  /* entity_id of the account that caused this change */
  operator        NUMERIC(12,0)
                  NOT NULL,

  /* entity_id of the changed entity */
  entity          NUMERIC(12,0)
                  NOT NULL,

  /* entity_id of an affected entity */
  target          NUMERIC(12,0),

  /* Additional metadata about the entities involved */
  metadata        JSON,

  /* Additional information about the change */
  params          JSON
);

category:main;
CREATE INDEX audit_log_operator_idx ON audit_log(operator);

category:main;
CREATE INDEX audit_log_entity_idx ON audit_log(entity);

category:main;
CREATE INDEX audit_log_target_idx ON audit_log(target);
