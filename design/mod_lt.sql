/*
 * This file is a UiO specific Cerebrum extension.
 *
 * The tables herein model the information from the UiO's HR system - LT.
 * The data structure is described in mod_lt.dia.
 */


category:drop;
drop TABLE lt_permisjon;

category:drop;
drop TABLE lt_reservasjon;

category:drop;
drop table lt_rolle;

category:drop;
drop table lt_gjest;

category:drop;
drop table lt_bilag;

category:drop;
drop table lt_tilsetting;

category:drop;
drop TABLE lt_permisjonskode;
category:drop;
drop table lt_rollekode;
category:drop;
drop table lt_gjestetypekode;
category:drop;
drop table lt_stillingskode;
category:drop;
drop table lt_lonnsstatus;





/* First, we create all code tables */

/* lonnsstatus -- codes describing various payment (lønn) categories */
category:code;
CREATE TABLE lt_lonnsstatus
(
	code		NUMERIC(6,0)
			NOT NULL
			CONSTRAINT lt_lonnsstatus_pk PRIMARY KEY,
	code_str 	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT lt_lonnsstatus_code_str_unique UNIQUE,
	description 	CHAR VARYING(512)
			NOT NULL
);


/* stillingskode -- codes describing various employments (stillinger) */
category:code;
CREATE TABLE lt_stillingskode
(
	code 		NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT lt_stillingskode_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
			NOT NULL
			CONSTRAINT lt_stillingskode_code_str_unique UNIQUE,
	description	CHAR VARYING(512)
			NOT NULL,
        hovedkategori   CHAR VARYING(3)
                        NOT NULL,
        tittel          CHAR VARYING(40)
                        NOT NULL
);


/* gjestetypekode -- codes describing guests at UiO */
category:code;
CREATE TABLE lt_gjestetypekode
(
	code		NUMERIC(6,0)
			NOT NULL
                        CONSTRAINT lt_gjestetypekode_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
                        NOT NULL
			CONSTRAINT lt_gjestetypekode_code_str_unique UNIQUE,
	description     CHAR VARYING(512)
                        NOT NULL,
        /* FIXME: what should this one be? */
        tittel          CHAR VARYING(10)
                        NOT NULL
);


/* rollekode -- codes describing various roles for people in Cerebrum */
category:code;
CREATE TABLE lt_rollekode
(
	code		NUMERIC(6,0)
			NOT NULL
                        CONSTRAINT lt_rollekode_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
                        NOT NULL
			CONSTRAINT lt_rollekode_code_str_unique UNIQUE,
	description     CHAR VARYING(512)
                        NOT NULL
);


/* permisjonskode -- codes describing various leaves of duty */
category:code;
CREATE TABLE lt_permisjonskode 
(       
	code		NUMERIC(6,0)
			NOT NULL
                        CONSTRAINT lt_permisjonskode_pk PRIMARY KEY,
	code_str	CHAR VARYING(16)
                        NOT NULL
			CONSTRAINT lt_permisjonskode_code_str_unique UNIQUE,
	description     CHAR VARYING(512)
                        NOT NULL
);





/* And now all the interesting tables */

/* Tilsetting -- employment records */
category:main;
CREATE TABLE lt_tilsetting
(
        tilsettings_id  NUMERIC(6,0)
                        NOT NULL,
        person_id       NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_tilsetting_person_id
                          REFERENCES person_info(person_id),
        ou_id           NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_tilsetting_ou_id
                          REFERENCES stedkode(ou_id),
        stillingskode   NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT lt_tilsetting_stillingskode
                          REFERENCES lt_stillingskode(code),
        dato_fra        DATE
                        NOT NULL,
        /* FIXME: What does NULL mean here? */
        dato_til        DATE,
        /* Employment percentage -- [0,100] */
        andel           NUMERIC(3,0)
                        NOT NULL,

	CONSTRAINT lt_tilsetting_pk PRIMARY KEY (tilsettings_id, person_id)
);


/* Bilag -- information about temporary employments */
category:main;
CREATE TABLE lt_bilag
(
        person_id       NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_bilag_person_id
                          REFERENCES person_info(person_id),
        ou_id           NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_bilag_ou_id
                          REFERENCES stedkode(ou_id),
        dato            DATE
                        NOT NULL,
        CONSTRAINT lt_bilag_pk PRIMARY KEY (person_id, ou_id)
);


/* Gjest -- information about guests at UiO */
category:main;
CREATE TABLE lt_gjest
(
        person_id       NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_gjest_person_id
                          REFERENCES person_info(person_id),
        ou_id           NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_gjest_ou_id
                          REFERENCES stedkode(ou_id),
        dato_fra        DATE
                        NOT NULL,
        gjestetypekode  NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT lt_gjest_gjestetypekode
                          REFERENCES lt_gjestetypekode(code),
        /* FIXME: What does NULL mean here? */
        dato_til        DATE,

        CONSTRAINT lt_gjest_pk PRIMARY KEY (person_id, ou_id, dato_fra)
);


/* Rolle -- information about roles played by various people */
category:main;
CREATE TABLE lt_rolle
(
        person_id       NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_rolle_person_id
                          REFERENCES person_info(person_id),
        ou_id           NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_rolle_ou_id
                          REFERENCES stedkode(ou_id),
        rollekode       NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT lt_rolle_rollekode
                          REFERENCES lt_rollekode(code),
        dato_fra        DATE
                        NOT NULL,
        /* FIXME: What does NULL mean here? */
        dato_til        DATE,

        CONSTRAINT lt_rolle_pk PRIMARY KEY (person_id, ou_id, rollekode)
);      


/* Reservasjon -- information about reservations against catalogue
   publishing */
category:main;
CREATE TABLE lt_reservasjon 
(       
        person_id       NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT lt_reservasjon_person_id
                          REFERENCES person_info(person_id)
                        CONSTRAINT lt_reservasjon_pk PRIMARY KEY,
        reservert       CHAR(1)
                        NOT NULL
                        CONSTRAINT lt_reservasjon_reservert_bool
                          CHECK (reservert IN ('T', 'F'))
);


/* Permisjon -- information about leaves of absence */
category:main;
CREATE TABLE lt_permisjon
(
        tilsettings_id  NUMERIC(6,0)
                        NOT NULL,
        person_id       NUMERIC(12,0)
                        NOT NULL,
        permisjonskode  NUMERIC(6,0)
                        NOT NULL
                        CONSTRAINT lt_permisjon_permisjonskode
                          REFERENCES lt_permisjonskode(code),
        dato_fra        DATE
                        NOT NULL,
        dato_til        DATE
                        NOT NULL,
	lonstatuskode	NUMERIC(6,0)
			NOT NULL
			CONSTRAINT lt_permisjon_lonstatuskode
			  REFERENCES lt_lonnsstatus(code),

        /* FIXME: Why does LT have such a strange type? This is still a
           percentage value */
        andel           NUMERIC(8,2)
                        NOT NULL,

        CONSTRAINT lt_permisjon_pk 
          PRIMARY KEY (tilsettings_id, person_id, permisjonskode, 
                       dato_fra, dato_til, lonstatuskode),

        CONSTRAINT lt_permisjon_tilsetting_fk FOREIGN KEY (tilsettings_id, person_id)
          REFERENCES lt_tilsetting(tilsettings_id, person_id)
);

