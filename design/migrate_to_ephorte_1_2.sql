/*
 * Copyright 2008 University of Oslo, Norway
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

/* SQL script for migrating a mod_ephorte 1.1 to 1.2 */
/* Create tables for ephorte-related permission registration */

category:pre;
CREATE TABLE ephorte_perm_type_code
(
  code          NUMERIC(6,0)
                CONSTRAINT ephorte_perm_type_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT ephorte_perm_type_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

category:pre;
CREATE TABLE ephorte_permission
(
  person_id       NUMERIC(12,0) 
  		  NOT NULL
		  CONSTRAINT ephorte_perm_person_id
		  REFERENCES person_info(person_id),
  perm_type       NUMERIC(6,0)
                  NOT NULL
                  CONSTRAINT ephorte_perm_type
                  REFERENCES ephorte_perm_type_code(code),
  adm_enhet       NUMERIC(12,0)
		    CONSTRAINT ephorte_perm_adm_enhet
		    REFERENCES ou_info(ou_id),
  start_date      DATE 
	 	  DEFAULT [:now]
		  NOT NULL,		 
  end_date        DATE,
  UNIQUE (person_id, perm_type, adm_enhet)
);