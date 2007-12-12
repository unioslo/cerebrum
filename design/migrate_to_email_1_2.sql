/*
 * Copyright 2007 University of Oslo, Norway
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

/* SQL script for migrating a mod_email 1.1 to 1.2 */
/* Create tables for new anti-spam tools registration */

category:pre;
CREATE TABLE email_target_filter_code
(
  code		NUMERIC(6,0)
		CONSTRAINT email_target_filter_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT email_target_filter_codestr_u UNIQUE,
  description	CHAR VARYING(512)
		NOT NULL
);

category:pre;
CREATE TABLE email_target_filter
(
  target_id	NUMERIC(12,0)
		CONSTRAINT email_target_filter_target_id
		  REFERENCES email_target(target_id),
  filter	NUMERIC(6,0)
		CONSTRAINT email_target_filter_filter
		  REFERENCES email_target_filter_code(code),
  CONSTRAINT email_target_filter_pk PRIMARY KEY (target_id, filter)
);