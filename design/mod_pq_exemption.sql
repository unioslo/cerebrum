/*
 * Copyright 2019 University of Oslo, Norway
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

/* tables used by Cerebrum.modules.no.uio.pq_exemption

  Stores whether or not a user should have a printer_quota. */

category:metainfo;
name=pq_exemption;
category:metainfo;
version=1.0;

category:drop;
DROP TABLE pq_exemption;

category:main;
CREATE TABLE pq_exemption
(
    person_id NUMERIC(12,0)
                REFERENCES person_info(person_id)
                CONSTRAINT printer_quotas_pk PRIMARY KEY,
    exempt BOOLEAN
                NOT NULL,
  CONSTRAINT person_info_entity_id
    FOREIGN KEY (person_id)
    REFERENCES entity_info(entity_id)
);
