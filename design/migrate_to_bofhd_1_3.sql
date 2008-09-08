/*
 * Copyright 2008 University of Oslo, Norway
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

/* SQL script for migrating a bofhd_tables 1.2 to 1.3 */

/* 
 * We need to be able to track client sessions based on IP. Thus, we need the
 * IP address itself.
 *
 * Additionally, the original schema forgot the FK to account_info (since only
 * accounts should be allowed to own sessions.
 */


/* first drop all the rows that we don't have the IP address for. This will
 * force the clients to re-authenticate, but they should survive 
 */
category:pre;
DELETE FROM bofhd_session_state;

category:pre;
DELETE FROM bofhd_session;

category:pre;
ALTER TABLE bofhd_session
  ADD COLUMN ip_address NUMERIC(10, 0) NOT NULL;

category:pre;
ALTER TABLE bofhd_session
  ADD CONSTRAINT bofhd_session_owner_fk
    FOREIGN KEY (account_id) 
    REFERENCES account_info(account_id);