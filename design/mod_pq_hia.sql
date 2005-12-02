/*
 * Copyright 2003, 2004 University of Oslo, Norway
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

category:metainfo;
name=pq;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE pquota_status;

category:main;
CREATE TABLE pquota_status (
 person_id           NUMERIC(12,0)
		       CONSTRAINT pquota_status_pk PRIMARY KEY	
                       CONSTRAINT pquota_status_person_id
                       REFERENCES person_info(person_id),
 term_quota_updated  CHAR(1)
                       CHECK (term_quota_updated IN ('V', 'H')),
 year_quota_updated  NUMERIC(4),
 total_quota         NUMERIC(12) 
);
