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

/***
 *** Module 'person_external_id_history' -- keep track of the change
 *** history of persons' external IDs.
 ***/
CREATE TABLE person_external_id_change
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_external_id_change_person_id
		  REFERENCES person(person_id),
  id_type	CHAR VARYING(16)
		CONSTRAINT person_external_id_change_id_type
		  REFERENCES person_external_id_code(code),
  change_date	DATE
		NOT NULL,
  source_system CHAR VARYING(16)
		CONSTRAINT person_external_id_change_source_system
		  REFERENCES authoritative_system_code(code),
  old_id	CHAR VARYING(256)
		NOT NULL,
  new_id	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT person_external_id_change_pk PRIMARY KEY
    (person_id, id_type, change_date, source_system)
);

/* arch-tag: 7d3a9dea-e9e4-4349-b060-534303750fc2
   (do not change this comment) */
