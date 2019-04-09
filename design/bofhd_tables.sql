/*
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
version=1.4;

category:main;
CREATE TABLE bofhd_session
(
  session_id   CHAR VARYING(32)
               CONSTRAINT bofhd_session_pk PRIMARY KEY
               NOT NULL,
  account_id   NUMERIC(12,0)
               CONSTRAINT bofhd_session_owner_fk
                 REFERENCES account_info(account_id)
               NOT NULL,
  auth_time    TIMESTAMP
               NOT NULL,
  last_seen    TIMESTAMP,
  /* IPv4 address is stored as a 32-bit integer */ 
  ip_address   NUMERIC(10,0) NOT NULL
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
  state_data   CHAR VARYING(512)
               NULL,
  set_time     TIMESTAMP
               NOT NULL
);

category:drop;
DROP TABLE bofhd_session_state;
category:drop;
DROP TABLE bofhd_session;
