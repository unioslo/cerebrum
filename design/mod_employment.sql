/* encoding: utf-8
 *
 * Copyright 2011-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.no.PersonEmployment
 *
 * This file is a Cerebrum extesion for tracking some of the employment
 * related data.
 *
 * Although affiliations could be used as a generic way of keeping track of
 * some of the employments, the available tables are insufficient to record
 * all the details we need. This module rectifies that.
 *
 * Note that this module exists parallel to the affiliations
 * registration. There is no connection (say, in a form of a foreign key)
 * between the two. It's like that by design.
 */
category:metainfo;
name=employment;

category:metainfo;
version=1.0;

category:drop;
DROP TABLE person_employment;


category:main;
CREATE TABLE person_employment
(
  person_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT person_employment_person_fk
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT person_employment_ou_fk
      REFERENCES ou_info(ou_id),

  /* Human-friendly string like 'Førsteamanuensis' or 'Janitor' */
  description
    CHAR VARYING(128)
    NOT NULL,

  source_system
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT person_employment_source_fk
      REFERENCES authoritative_system_code(code),

  /* When applicable, a (typically) 4-digit state employee code */
  employment_code
    CHAR VARYING(16)
    NULL,

  main_employment
    CHAR (1)
    DEFAULT 'T'
    NOT NULL
    CONSTRAINT main_employment_bool
      CHECK (main_employment IN ('T', 'F')),

  percentage
    NUMERIC(5, 2)
    NOT NULL,

  start_date
    DATE
    NOT NULL,

  end_date
    DATE
    NOT NULL,

  CONSTRAINT person_employment_pk
    PRIMARY KEY (person_id, ou_id, description, source_system)
);


category:main;
CREATE INDEX person_employment_pid_index ON person_employment(person_id);

category:main;
CREATE INDEX person_employment_ou_id_index ON person_employment(ou_id);

category:main;
CREATE INDEX person_employment_source_id_index ON person_employment(source_system);

category:main;
CREATE INDEX person_employment_emp_code_index ON person_employment(employment_code);
