/*
 * Copyright 2003, 2004 University of Oslo, Norway
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

/* Tables for storing state in the bofhd server.  The tables are
  intended for internal bofhd use only.
*/

/* bofhd_session

  session_id : unique PK
  account_id : associated authenticated session.  If it was
      FK(account), extra code would be needed in delete_account
  auth_time : time-stamp for last authentication
*/

category:metainfo;
name=bofhd;
category:metainfo;
version=1.0;

category:main;
CREATE TABLE bofhd_session
(
  session_id   CHAR VARYING(32)
               CONSTRAINT bofhd_session_pk PRIMARY KEY
               NOT NULL,
  account_id   NUMERIC(12,0)
               NOT NULL,
  auth_time    TIMESTAMP
               NOT NULL,
  last_seen    TIMESTAMP
);

/* bofhd_session_state

  session_id : FK to  bofhd_session
  state_type : identifies the type of state, i.e set_passwd
  entity_id  : affected entity_id
  state_data : data
  set_time   : time-stamp

  TBD:  do we want entity_id?
*/

category:main;
CREATE TABLE bofhd_session_state
(
  session_id   CHAR VARYING(32)
               CONSTRAINT bofhd_session_state_fk 
                 REFERENCES bofhd_session(session_id)
               NOT NULL,
  state_type   CHAR VARYING(32)
               NOT NULL,
  entity_id    NUMERIC(12,0)
               NULL,
  state_data   CHAR VARYING(80)
               NULL,
  set_time     TIMESTAMP
               NOT NULL
);

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
  state_data   CHAR VARYING(80)
               NULL
);

category:drop;
DROP TABLE bofhd_request;
category:drop;
DROP TABLE bofhd_request_code;
category:drop;
DROP TABLE bofhd_session_state;
category:drop;
DROP TABLE bofhd_session;
category:drop;
DROP SEQUENCE request_id_seq;

/* arch-tag: 36c03c76-7ffe-4f84-b080-7e92073fd119
   (do not change this comment) */
