/*
 * Copyright 2002 University of Oslo, Norway
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

/*	notur_user



*/
CREATE TABLE notur_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT notur_user_account_id
		  REFERENCES posix_user(account_id)
		CONSTRAINT notur_user_pk PRIMARY KEY,
  notur_uid	NUMERIC(10,0)
		NOT NULL,
/* TBD: Trenger vi en egen verdidomene-kolonne for UIDer her?  NoTuR
	spiser jo på en måte av alle de involverte institusjonenes
	egne UID-rom, men har på en annen måte fått tilordnet seg sin
	egen range innenfor hver av disse. */
  uid_domain	CHAR VARYING(16)
		CONSTRAINT notur_user_uid_domain
		  REFERENCES value_domain_code(code)
);


/*	notur_site_user

  'name' and 'dir' defaults to the corresponding values from the
  parent posix_user.

*/
CREATE TABLE notur_site_user
(
  account_id	NUMERIC(12,0)
		CONSTRAINT notur_site_user_account_id
		  REFERENCES notur_user(account_id),
  notur_domain	CHAR VARYING(16)
		CONSTRAINT notur_site_user_notur_domain
		  REFERENCES value_domain_code(code),
/* TBD: Vil UNIQUE-constrainten nederst fungere som den skal dersom
	'name' tillates å kunne være NULL? */
  name		CHAR VARYING(8),
  dir		CHAR VARYING(64),
  CONSTRAINT notur_site_user_pk PRIMARY KEY(account_id, notur_domain),
  CONSTRAINT notur_site_user_unique UNIQUE(notur_domain, user_name)
);

/* arch-tag: c97b6767-c98e-4577-bc8f-a70f7257bd25
   (do not change this comment) */
