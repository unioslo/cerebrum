/*
 * Copyright 2004 University of Oslo, Norway
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

/* SQL script for migrating a pre 0.9.2 database to 0.9.2
*/
category:pre;
CREATE TABLE home_status_code (
  code          NUMERIC(6,0)
                CONSTRAINT home_status_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT home_status_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

category:pre;
CREATE TABLE account_home (
  account_id    NUMERIC(12,0)
                CONSTRAINT account_home_fk 
                REFERENCES account_info(account_id),
  spread        NUMERIC(6,0) NOT NULL
		CONSTRAINT account_home_spread
		  REFERENCES spread_code(code),
  home          CHAR VARYING(512),
  disk_id       NUMERIC(12,0)
                CONSTRAINT account_info_disk_id REFERENCES disk_info(disk_id),
  status        NUMERIC(6,0) NOT NULL
                CONSTRAINT home_status_code
                  REFERENCES home_status_code(code),
  CONSTRAINT account_home_pk
    PRIMARY KEY (account_id, spread)
);

category:pre;
CREATE TABLE cerebrum_metainfo (
  name		CHAR VARYING(80)
		CONSTRAINT cerebrum_metainfo_pk PRIMARY KEY,
  value		CHAR VARYING(1024) NOT NULL
);

category:post;
ALTER TABLE account_info DROP COLUMN disk_id;
category:post;
ALTER TABLE account_info DROP COLUMN home;

/* arch-tag: 6bc03197-1d6c-4b77-b939-6fc10887eb0a
   (do not change this comment) */
