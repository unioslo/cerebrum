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
 *
 * Tables used by Cerebrum.modules.ou_disk_mapping
 *
 * This module stores settings related to an organizational unit. Initially
 * this is used for saving the defauly homedir for combinations of
 * Organizational Unit, Person Affiliation, and Affiliation Status.
 */
category:metainfo;
name=ou_disk_mapping;

category:metainfo;
version=1.0;

/**
 * Table to map disk paths to ou and affiliation.
 *
 * ou_id
 *   Entity id of an OU in the ou_info table
 * aff_code
 *   Code of an Affiliation in the person_affiliation_code table
 * status_code or null
 *   Code of an Affiliation status in the person_aff_status_code table
 * disk_id or null
 *   Entity id of a Disk in the disk_info table
**/
category:main;
CREATE TABLE ou_disk_mapping(
   ou_id       NUMERIC(12, 0) NOT NULL REFERENCES ou_info (ou_id),
   aff_code    NUMERIC(12, 0) REFERENCES person_affiliation_code (code),
   status_code NUMERIC(12, 0) REFERENCES person_aff_status_code (status),
   disk_id     NUMERIC(12, 0) NOT NULL REFERENCES disk_info (disk_id),
   CONSTRAINT ou_disk_mapping_unique UNIQUE (ou_id, aff_code, status_code),
   CONSTRAINT ou_disk_mapping_statuswoaff CHECK (NOT (aff_code IS NULL AND NOT
   status_code IS NULL))
);

/**
 * Indexes needed to allow NULL values for aff_code and status_code.
 * Note that we do not allow NULL for aff_code if status_code is set.
**/
category:main;
CREATE UNIQUE INDEX ou_disk_mapping_statusnull_idx ON ou_disk_mapping (ou_id, aff_code)
WHERE status_code IS NULL;

category:main;
CREATE UNIQUE INDEX ou_disk_mapping_bothnull_idx ON ou_disk_mapping (ou_id)
WHERE aff_code IS NULL
  AND status_code IS NULL;

category:drop;
DROP INDEX ou_disk_mapping_bothnull_idx;

category:drop;
DROP INDEX ou_disk_mapping_statusnull_idx;

category:drop;
DROP TABLE ou_disk_mapping;
