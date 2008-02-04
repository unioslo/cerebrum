/*
 * Copyright 2007 University of Oslo, Norway
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

/* SQL script for migrating a mod_ephorte 1.0 to 1.1 */


/* Add a column auto_role to differ automatic roles from roles given
 * manually in bofh.
 */
category:pre;
ALTER TABLE ephorte_role ADD COLUMN auto_role CHAR(1)
      CONSTRAINT auto_rolle_bool_chk CHECK(auto_role IN ('T', 'F'));

/* Make constraint to person_info(person_id) so that persons cannot be
 * deleted without first removing any ephorte roles. 
 */
category:pre;
ALTER TABLE ephorte_role ADD CONSTRAINT ephorte_role_person_id 
      FOREIGN KEY (person_id) REFERENCES person_info(person_id);

/* Make unique constraint on coloumns person_id, role_type, adm_enhet,
 * arkivdel, journalenhet in table ephorte_role. It shouldn't be
 * possible to add the same role twice. 
 */
category:pre;
ALTER TABLE ephorte_role ADD CONSTRAINT ephorte_role_unique
      UNIQUE (person_id, role_type, adm_enhet, arkivdel, journalenhet);
