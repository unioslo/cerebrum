/*
 * Copyright 2003 University of Oslo, Norway
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
 *
 */


/*	country_alias

  When importing data with human-readable addresses, we need a
  mechanism for translating country name variants into the
  corresponding entry in the country_code table.

  alias: Washed aliases for the name of the country; the washing
	 consists of asciifying and uppercasing.

*/
category:main;
CREATE TABLE country_alias
(
  alias		CHAR VARYING(64)
		CONSTRAINT country_alias_alias_pk PRIMARY KEY,
  country_code	NUMERIC(6,0)
		NOT NULL
		CONSTRAINT country_alias_country_code
		  REFERENCES country_code(code)
);
categrory:drop;
DROP TABLE country_alias;
