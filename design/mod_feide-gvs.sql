/*
 * Copyright 2002, 2003 University of Oslo, Norway
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
 */


/*
  Define the categories of relations between guardian and pupil.
*/

category:code;
CREATE TABLE feide_guardian_code
(
  code		NUMERIC(6,0)
		CONSTRAINT feide_guardian_code_pk PRIMARY KEY,
  code_str	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT feide_guardian_codestr_u UNIQUE,
  relation	CHAR VARYING(512)
		NOT NULL
		CONSTRAINT feide_guardian_code_relation_u UNIQUE
);


/*
  Define relations between pupils and guardians(parents).
*/

category:code;
CREATE TABLE feide_guardian_pupil
(
  guartdian_id	NUMERIC(12,0)
		CONSTRAINT feide_guardian_pupil_guardian_id
		  REFERENCES person_info(person_id),
  pupil_id	NUMERIC(12,0)
		CONSTRAINT feide_guardian_pupil_pupil_id
		  REFERENCES person_info(person_id)
);


category:code;
CREATE TABLE feide_teacher_school
(
  teacher_id	NUMERIC(12,0)
		CONSTRAINT feide_teacher_school_teacher_id
		  REFERENCES person_info(person_id),
  ou_id		NUMERIC(12,0)
		CONSTRAINT feide_teacher_school_scchool_id
		  REFERENCES person_info(person_id)
);



category:code;
CREATE TABLE feide_program
(
  program_id	NUMERIC(12,0)
		CONSTRAINT feide_program_pk PRIMARY KEY
  class_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT feide_program_class_id
		  REFERENCES group(group_id),
  course_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT feide_program_course_id
		  REFERENCES group(group_id),
  name		CHAR VARYING(512)
		NOT NULL,
  teacher_id    NUMERIC(12,0)
);


category:drop;
DROP TABLE feide_guardian_pupil;
category:drop;
DROP TABLE feide_guardian_code;
category:drop;
DROP TABLE feide_teacher_school;
category:drop;
DROP TABLE feide_program;


/*

Dumped designs. Hangs around for future (mis)use.

category:code;
CREATE TABLE feide_pupil_course
(
  person_id	 NUMERIC(12,0)

  course_id      NUMERIC(12,0)
);

category:code;
CREATE TABLE feide_pupil_class
(
  person_id	NUMERIC(12,0)

  class_id      NUMERIC(12,0)
);

category:code;
CREATE TABLE feide_course
(
  course_id	NUMERIC(12,0)
                CONSTRAINT feide_course_pk PRIMARY KEY,
  name		CHAR VARYING(512)
		NOT NULL
);

category:code;
CREATE TABLE feide_class
(
  class_id	NUMERIC(12,0)
		CONSTRAINT feide_class_pk PRIMARY KEY,
  name		CHAR VARYING(512)
		NOT NULL
);
*/

