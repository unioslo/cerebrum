/*
 * Copyright 2005 University of Oslo, Norway
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

/* SQL script for migrating a 0.9.5 database to 0.9.6 */


/* Change the primary key for the person_aff_status_code table */
category:pre;
ALTER TABLE person_affiliation_source DROP CONSTRAINT person_aff_src_status;
category:pre;
ALTER TABLE person_aff_status_code DROP CONSTRAINT person_aff_status_code_pk;
category:pre;
ALTER TABLE person_aff_status_code ADD CONSTRAINT person_aff_status_code_a_s_u UNIQUE (affiliation, status);
category:pre;
ALTER TABLE person_aff_status_code ADD CONSTRAINT person_aff_status_code_pk PRIMARY KEY (status);
category:pre;
ALTER TABLE person_affiliation_source ADD CONSTRAINT person_aff_src_status FOREIGN KEY (affiliation, status) REFERENCES person_aff_status_code(affiliation, status);
category:pre;
ALTER TABLE person_aff_status_code ALTER COLUMN affiliation SET NOT NULL;
