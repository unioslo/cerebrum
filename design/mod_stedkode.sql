/***********************************************************************
 *** Modules related to OU. ********************************************
 ***********************************************************************/


/***
 *** Module `stedkode' -- specific to the higher education sector in
 *** Norway.
 ***/

/*	stedkode



*/
CREATE TABLE stedkode
(
  ou_id		NUMERIC(12,0)
		CONSTRAINT stedkode_pk PRIMARY KEY
		CONSTRAINT stedkode_ou_id REFERENCES ou(ou_id),
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
