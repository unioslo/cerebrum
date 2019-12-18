/*
 * Copyright 2004-2019 University of Oslo, Norway
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
 *
 * This file is a Cerebrum extension. It contains the schema necessary to
 * support SAP-SSØ functionality in Cerebrum.
 *
 * See:
 *  - Cerebrum/modules/no/Constants.py
 *  - contrib/no/hia/process_SAP_affiliations.py
 */
category:metainfo;
name=sap;

category:metainfo;
version=1.1;


/* SAP.STELL */
category:drop;
DROP TABLE sap_stillingstype;

category:drop;
DROP TABLE sap_lonnstittel;


/* The code tables first */

/*
 * sap_stillingstype -- codes describing employment categories
 * (hovedstilling, bistilling, etc.)
 */
category:code;
CREATE TABLE sap_stillingstype
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT sap_stillingstype_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT sap_stillingstype_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*
 * sap_lonnstittel -- codes describing employments (SAP.STELL, lønnstittel).
 * This is a magic number uniquely identifying the specific position
 * (lecturer, professor, librarian, janitor, etc.)
 */
category:code;
CREATE TABLE sap_lonnstittel
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT sap_lonnstittel_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT sap_lonnstittel_code_str_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL,

  kategori
    CHAR(3)
    NOT NULL
);
