/*
 * Copyright 2002, 2003 University of Oslo, Norway
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


/***********************************************************************
 *** Modules related to OU. ********************************************
 ***********************************************************************/
category:metainfo;
name=stedkode;
category:metainfo;
version=1.0;


/***
 *** Module `stedkode' -- specific to the higher education sector in
 *** Norway.
 ***/

category:code/Oracle;
CREATE ROLE read_mod_stedkode NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_stedkode NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_stedkode TO change_mod_stedkode;

category:drop/Oracle;
GRANT read_mod_stedkode TO read_core_table;
category:drop/Oracle;
GRANT change_mod_stedkode TO change_core_table;


/*	stedkode



*/
category:main;
CREATE TABLE stedkode
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT stedkode_pk PRIMARY KEY
		CONSTRAINT stedkode_ou_id REFERENCES ou_info(ou_id),
  landkode	NUMERIC(3,0)
		NOT NULL,
  institusjon	NUMERIC(5,0)
		NOT NULL,
  fakultet	NUMERIC(2,0)
		NOT NULL,
  institutt	NUMERIC(2,0)
		NOT NULL,
  avdeling	NUMERIC(2,0)
		NOT NULL,
  katalog_merke	CHAR(1)
		NOT NULL
		CONSTRAINT stedkode_katalog_merke_bool
		  CHECK (katalog_merke IN ('T', 'F')),
  CONSTRAINT stedkode_kode UNIQUE (institusjon, fakultet, institutt, avdeling)
);
category:main/Oracle;
GRANT SELECT ON stedkode TO read_mod_stedkode;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE ON stedkode TO change_mod_stedkode;


category:drop;
DROP TABLE stedkode;

category:drop/Oracle;
DROP ROLE change_mod_stedkode;
category:drop/Oracle;
DROP ROLE read_mod_stedkode;

/* arch-tag: 17913c75-9f94-4064-a462-acdd2e785aa3
   (do not change this comment) */
