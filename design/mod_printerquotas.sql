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
name=printerquotas;
category:metainfo;
version=1.0;
category:drop;
DROP TABLE printerquotas;

category:main;
CREATE TABLE printerquotas (
 account_id           NUMERIC(12,0)
                      CONSTRAINT printerquotas_pk PRIMARY KEY
                      CONSTRAINT printerquotas_account_id
                      REFERENCES account_info(account_id),
 printer_quota        NUMERIC(8),
 pages_printed        NUMERIC(8),
 pages_this_semester  NUMERIC(8),
 termin_quota         NUMERIC(8),
 has_printerquota     CHAR(1)
		NOT NULL
		CONSTRAINT printerquotas_has_pq_bool
		  CHECK (has_printerquota IN ('T', 'F')),
 weekly_quota         NUMERIC(8),
 max_quota            NUMERIC(8)
);

/* arch-tag: 21c9c20a-90ba-4366-b628-32697837ae03
   (do not change this comment) */
