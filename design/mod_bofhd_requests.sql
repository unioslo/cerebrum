/*
 * Copyright 2019 University of Oslo, Norway
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
name=bofhd_requests;
category:metainfo;
version=1.0;

/* bofhd request operation types */

category:code;
CREATE TABLE bofhd_request_code
(
  code          NUMERIC(6,0)
                CONSTRAINT bofhd_request_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT bofhd_request_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

/* bofhd_request contains pending requests like "move batch".
  - account_id of "requester"
  - run_at not-null iff action should be executed (unlike "move
    request")
  - entity_id - identifies the entity affected by the request
  - destination_id :
     disk_id for: br_move_user, br_move_request
     None for: br_move_student
     group_id for: br_move_give
TBD: It may be desireable to have a request_id to prevent things like
     "user move cancel" from removing all entries.
TBD: It may or may not be a better idea to store the command vector
sent to bofhd to execute the command.
*/

category:main;
CREATE SEQUENCE request_id_seq;
category:main;
CREATE TABLE bofhd_request
(
  request_id   NUMERIC(12,0)
               CONSTRAINT bofhd_request_pk PRIMARY KEY,
  requestee_id  NUMERIC(12,0),
  run_at        TIMESTAMP NULL,
  operation     NUMERIC(6,0)
                NOT NULL
                CONSTRAINT operation_code
                  REFERENCES bofhd_request_code(code),
  entity_id     NUMERIC(12,0),
  destination_id NUMERIC(12,0),
  state_data   CHAR VARYING(4096) NULL
);

category:drop;
DROP TABLE bofhd_request;
category:drop;
DROP TABLE bofhd_request_code;
category:drop;
DROP SEQUENCE request_id_seq;
