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
 *** Module 'name-history' -- keep track of persons' names as they
 *** change over time.
 ***/
CREATE TABLE person_name_history
(
  person_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT person_name_history_person_id
		  REFERENCES person(person_id),
  name_variant	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_name_variant
		  REFERENCES person_name_code(code),
  source_system	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_source_system
		  REFERENCES authoritative_system_code(code),
  entry_date	DATE
		NOT NULL,
/* Must allow NULL names to indicate that a person have seized to have
   a value for one name_variant. */
  name		CHAR VARYING(256)
);

/* arch-tag: 429df112-847f-44d5-a8e9-5f10c9f64f9e
   (do not change this comment) */
