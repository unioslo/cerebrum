/*
 * This file is a HiA specific Cerebrum extension. 
 * 
 * The tables herein model the information from HiA's HR system - SAP.
 * The data structure is described in mod_sap.dia.
 */

category:drop;
DROP TABLE sap_rolle;

category:drop;
DROP TABLE sap_OU;

category:drop;
DROP TABLE sap_tilsetting;

category:drop;
DROP TABLE sap_person;


/* code tables */

category:drop;
DROP TABLE sap_forretningsomrade;

/* SAP.STELL */
category:drop;
DROP TABLE sap_lonnstittel;

category:drop;
DROP TABLE sap_permisjon;

category:drop;
DROP TABLE sap_utvalg;

category:drop;
DROP TABLE sap_stillingstype;




/* The code tables first */

/* 
 * sap_stillingstype -- codes describing employment categories
 * (hovedstilling, bistilling, etc.)
 */
category:code;
CREATE TABLE sap_stillingstype
(
	code 		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_stillingstype_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT sap_stillingstype_code_str_unique UNIQUE,
	description 	CHAR VARYING(512)
			NOT NULL
);


/* sap_utvalg -- codes describing committees (utvalg) */
category:code;
CREATE TABLE sap_utvalg
(
	code		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_utvalg_pk PRIMARY KEY,
        /* FIXME: this is a bit non-standard 
           (our codes are normally 16 chars wide) */
	code_str	CHAR VARYING(40)
			NOT NULL
			CONSTRAINT sap_utvalg_code_str_unique UNIQUE,
	description	CHAR VARYING(512)
			NOT NULL
);


/* sap_permisjon -- codes describing leaves of absence */
category:code;
CREATE TAble sap_permisjon
(
	code		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_permisjon_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT sap_permisjon_code_str_unique UNIQUE,
	description	CHAR VARYING(512)
			NOT NULL
);


/* sap_lonnstittel -- codes describing employments (SAP.STELL, lønnstittel) */
category:code;
CREATE TAble sap_lonnstittel
(
	code		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_lonnstittel_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT sap_lonnstittel_code_str_unique UNIQUE,
	description	CHAR VARYING(512)
			NOT NULL,
	/* FIXME: should there be a constraint here -- 
           kategori IN ('VIT', 'ØVR') */
	kategori	CHAR(3)
			NOT NULL
);



/* sap_forretningsomrade -- codes describing various geographical areas */
category:code;
CREATE TAble sap_forretningsomrade
(
	code		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_forretningsomrade_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT sap_forretningsomrade_code_str_unique UNIQUE,
	description	CHAR VARYING(512)
			NOT NULL
);





/* And now, the "interesting" tables :) */

/* sap_person -- information about people (employees, actually) from SAP */
category:main;
CREATE TABLE sap_person
(
	person_id	NUMERIC(12,0)
			NOT NULL
			CONSTRAINT sap_person_pk PRIMARY KEY
			CONSTRAINT sap_person_person_id_fk 
 			  REFERENCES person_info(person_id),
	fo_kode		NUMERIC(6,0) 
			NOT NULL
			CONSTRAINT sap_person_fo_kode_fk
			  REFERENCES sap_forretningsomrade(code),
	sprak		NUMERIC(6,0)
			CONSTRAINT sap_person_sprak_fk
			  REFERENCES language_code(code),
	permisjonskode	NUMERIC(6,0)
			CONSTRAINT sap_person_permisjonskode_fk
			  REFERENCES sap_permisjon(code),
	permisjonsandel NUMERIC(3,0)
);
category:main;
CREATE INDEX sap_person_person_id_index ON sap_person(person_id);


/* sap_tilsetting -- information on employments (tilsettinger) */
/* FIXME: PK? */
category:main;
CREATE TABLE sap_tilsetting 
(
	person_id	NUMERIC(12,0)
			NOT NULL
			CONSTRAINT sap_tilsetting_person_id_fk
			  REFERENCES person_info(person_id),
	ou_id		NUMERIC(12,0)
			NOT NULL
			CONSTRAINT sap_tilsetting_ou_id_fk
			  REFERENCES ou_info(ou_id),
	lonnstittel	NUMERIC(6,0)
			CONSTRAINT sap_tilsetting_lonnstittel_fk 
			  REFERENCES sap_lonnstittel(code),

	/* 
	 * FIXME: This is a bit scary -- we have some magic ID (which we
	 * have no control over) as a part of the PK. We have really no
	 * chance of controlling that sensible data are inserted
	 * here. Should anything go wrong with SAP datafile, we risk
	 * polluting Cerebrum with nonsensical data.
	 */
	funksjonstittel	NUMERIC(8,0) 
			NOT NULL,
	/* hoved/bistilling (or whatever :)) */
	/* FIXME: Should this have a constraint on */
	stillingstype	NUMERIC(6,0)
			CONSTRAINT sap_tilsetting_stillingstype_fk
			  REFERENCES sap_stillingstype(code),
	dato_fra	DATE,
	dato_til	DATE,
	/* These can be fractional */
	andel		NUMERIC(5,2),

	CONSTRAINT sap_tilsetting_pk PRIMARY KEY 
          (person_id, ou_id, funksjonstittel)
);
category:main;
CREATE INDEX sap_tilsetting_person_id_index ON sap_tilsetting(person_id);



/* sap_ou -- information on OUs in SAP */
/* This table is used to map SAP OU identifications to Cerebrum's ou_ids */
category:main;
CREATE TABLE sap_ou
(
	ou_id		NUMERIC(12,0)
			NOT NULL
			CONSTRAINT sap_ou_ou_id_fk 
			  REFERENCES ou_info(ou_id)
			CONSTRAINT sap_ou_ou_id_pk PRIMARY KEY,
	orgeh		CHAR(8) 
			NOT NULL,
	fo_kode		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_ou_fo_kode_fk
			  REFERENCES sap_forretningsomrade(code),
	CONSTRAINT sap_ou_sap_id_unique UNIQUE (orgeh, fo_kode)
);
category:main;
CREATE INDEX sap_ou_ou_id_index ON sap_ou(ou_id);
category:main;
CREATE INDEX sap_ou_orgeh_fo_kode_index ON sap_ou(orgeh, fo_kode);



/* sap_rolle -- information on roles held by various people */
category:main;
CREATE TABLE sap_rolle
(
	person_id	NUMERIC(12,0)
			NOT NULL
			CONSTRAINT sap_rolle_person_id_fk 
			  REFERENCES person_info(person_id),
	utvalg		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT sap_rolle_utvalg_fk
			  REFERENCES sap_utvalg(code),
	/* NB! This might have to become a FK to its own code table */
	utvalgsrolle	CHAR VARYING(30),
	dato_fra	DATE,
	dato_til	DATE,

	CONSTRAINT sap_rolle_pk PRIMARY KEY (person_id, utvalg)

	/* 
	 * NB! fo_kode is not necessary here, since we can find it by using
	 * ou_id.
	 */
);
category:main;
CREATE INDEX sap_rolle_person_id_index ON sap_rolle(person_id);

			
