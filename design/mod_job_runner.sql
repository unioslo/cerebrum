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

category:main;
CREATE TABLE job_ran
(
  id           CHAR VARYING(32)
               CONSTRAINT job_ran_pk
               PRIMARY KEY,
  timestamp    TIMESTAMP
               NOT NULL
);

category:drop;
DROP TABLE job_ran;

/* arch-tag: aa468296-bbb1-427f-aac9-cdeedeabf59a
   (do not change this comment) */
