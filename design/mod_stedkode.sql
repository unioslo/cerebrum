/***********************************************************************
 *** Modules related to OU. ********************************************
 ***********************************************************************/


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
  institusjon	NUMERIC(4,0)
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
