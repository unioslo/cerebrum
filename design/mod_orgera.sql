/* encoding: utf-8
 *
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
 * Tables used by Cerebrum.modules.no.orgera
 *
 * This module contains information about organizational roles, according to the
 * ORG-ERA access model.
 *
 */
category:metainfo;
name=orgera;

category:metainfo;
version=0.1;


/**
 * Set of known SKO values (stillingskode/job code)
 *
 * Not to be confused with "stedkode" (location code, also abbreviated as SKO).
 *
 * sko
 *   "Stillingskode".  A numerical category code for a given work placement.
 *
 * description
 *   A title or short text to describe the given code.
 *
 * Examples:
 *   1004 - Rektor
 *   1065 - Konsulent
**/
category:main;
CREATE TABLE IF NOT EXISTS orgera_stillingskode
(
  sko
    NUMERIC(4,0)
    NOT NULL,

  description
    TEXT
    NOT NULL,

  CONSTRAINT orgera_stillingskode_pk PRIMARY KEY (sko)
);


/**
 * Set of known STYRK values (yrkeskode/occupation code)
 *
 * sko
 *   A numerical job code that this occuopation code belongs to
 *
 * styrk
 *   A numerical category code for a given occupation.
 *
 * description
 *   A title or short text to describe the given code.
 *
 * Examples:
 *   (1065, 3120126): Konsulent, IT-medarbeider
 *   (1065, 3415116): Konsulent, Salgsmedarbeider
**/
category:main;
CREATE TABLE IF NOT EXISTS orgera_yrkeskode
(
  sko
    NUMERIC(4,0)
    NOT NULL,

  styrk
    NUMERIC(9,0)
    NOT NULL,

  description
    TEXT
    NOT NULL,

  CONSTRAINT orgera_yrkeskode_pk PRIMARY KEY (sko, styrk)
);


/**
 * Current assignments for a given employee.
 *
 * Assignments are similar to affiliations, in that they bind a given person to
 * a given OU.
 *
 * source_system
 *   Identifies which source the assignment comes from
 *
 * assignment_id
 *   A unique identifier for this assignment, typically from the source system
 *
 * person_id
 *   Person this specific assignment belongs to.
 *
 * ou_id
 *   OU this specific person is assigned to.
 *
 * sko
 *   A sko-descriptor for the given assignment.
 *
 * styrk
 *   An styrk-descriptor for the given assignment. Not all assignments will have
 *   an styrk-code, so this field is nullable.
 *
 * We could optionally extend this table with other assignment data or flags.
**/
category:main;
CREATE TABLE IF NOT EXISTS orgera_assignments
(
  source_system
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT orgera_assignments_source_fk
      REFERENCES authoritative_system_code(code),

  assignment_id
    CHAR VARYING(128)
    NOT NULL,

  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT orgera_assignments_person_fk
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT orgera_assignments_ou_fk
      REFERENCES ou_info(ou_id),

  sko
    NUMERIC(4,0)
    NOT NULL
    CONSTRAINT orgera_assignments_sko_fk
      REFERENCES orgera_stillingskode(sko),

  styrk
    NUMERIC(9,0)
    NULL,

  updated_at
    TIMESTAMP WITH TIME ZONE
    NOT NULL
    DEFAULT [:now],

  CONSTRAINT orgera_assignments_pk
    PRIMARY KEY (source_system, assignment_id),

  CONSTRAINT orgera_assignments_styrk_fk
    FOREIGN KEY (sko, styrk)
    REFERENCES orgera_yrkeskode(sko, styrk)
);


/* function to create a trigger that sets updated_at */
category:main;
CREATE OR REPLACE FUNCTION orgera_assignments_set_update()
RETURNS TRIGGER AS '
  BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
  END;
' LANGUAGE plpgsql;

/* Add trigger to automatically set orgera_assignments.updated_at */
category:main;
CREATE TRIGGER orgera_assignments_set_update_trigger
    BEFORE UPDATE ON orgera_assignments
    FOR EACH ROW
    EXECUTE PROCEDURE orgera_assignments_set_update();

category:main;
CREATE INDEX orgera_assignments_person_idx ON orgera_assignments(person_id);

category:drop;
DROP INDEX IF EXISTS orgera_assignments_person_idx;

category:main;
CREATE INDEX orgera_assignments_ou_idx ON orgera_assignments(ou_id);

category:drop;
DROP INDEX IF EXISTS orgera_assignments_ou_idx;

category:main;
CREATE INDEX orgera_assignments_sko_idx ON orgera_assignments(sko);

category:drop;
DROP INDEX IF EXISTS orgera_assignments_sko_idx;

category:main;
CREATE INDEX orgera_assignments_styrk_idx ON orgera_assignments(styrk);

category:drop;
DROP INDEX IF EXISTS orgera_assignments_styrk_idx;

category:drop;
DROP TRIGGER IF EXISTS orgera_assignments_set_update_trigger ON orgera_assignments;

category:drop;
DROP FUNCTION IF EXISTS orgera_assignments_set_update();

category:drop;
DROP TABLE IF EXISTS orgera_assignments;


category:drop;
DROP TABLE IF EXISTS orgera_stillingskode;


category:drop;
DROP TABLE IF EXISTS orgera_yrkeskode;
