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
 */

/**********************************************************************
 *** Modules related to building . ************************************
 **********************************************************************/
category:metainfo;
name=building;
category:metainfo;
version=1.0;

/***
 *** Module 'building' 
 ***/
category:code/Oracle;
CREATE ROLE read_mod_building NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_building NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_building TO change_mod_building;

category:drop/Oracle;
GRANT read_mod_building TO read_core_table;
category:drop/Oracle;
GRANT change_mod_building TO change_core_table;

/* building

*/
category:main;
CREATE TABLE building
(
   building_id  NUMERIC(12,0)
        CONSTRAIN building_pk PRIMARY KEY,
   name     VARCHAR(128,0) 
        NOT NULL,
   description  VARCHAR(256,0)
);
category:main/Oracle;
GRANT SELECT ON building TO read_mod_building;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE on building TO change_mod_building;

category:drop;
DROP TABLE building;

category:drop/Oracle;
DROP ROLE change_mod_building;
category:drop/Oracle;
DROP ROLE read_mod_building;

/**********************************************************************
 *** Modules related to room . ****************************************
 **********************************************************************/
category:metainfo;
name=room;
category:metainfo;
version=1.0;

/***
 *** Module 'room' 
 ***/
category:code/Oracle;
CREATE ROLE read_mod_room NOT IDENTIFIED;
category:code/Oracle;
CREATE ROLE change_mod_room NOT IDENTIFIED;
category:code/Oracle;
GRANT read_mod_room TO change_mod_room;

category:drop/Oracle;
GRANT read_mod_room TO read_core_table;
category:drop/Oracle;
GRANT change_mod_room TO change_core_table;

/* room

*/
category:main;
CREATE TABLE room
(
   room_id  NUMERIC(12,0)
        CONSTRAIN room_pk PRIMARY KEY,
   name     VARCHAR(128,0) 
        NOT NULL,
   building NUMERIC(12,0) 
        NOT NULL
        CONSTRAINT REFERENCES building(building_id),
   description  VARCHAR(256,0)
);
category:main/Oracle;
GRANT SELECT ON room TO read_mod_room;
category:main/Oracle;
GRANT INSERT, UPDATE, DELETE on room TO change_mod_room;

category:drop;
DROP TABLE room;

category:drop/Oracle;
DROP ROLE change_mod_room;
category:drop/Oracle;
DROP ROLE read_mod_room;

/* arch-tag: 43654858-af80-11da-8a6f-477d3cf29b2a
   (do not change this comment) */
