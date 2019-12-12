/* encoding: utf-8
 *
 * Copyright 2003-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.event_publisher
 */
category:metainfo;
name=feidegvs;

category:metainfo;
version=1.0;


/*
 * Define the categories of relations between guardian and pupil.
 */
category:code;
CREATE TABLE feide_gvs_guardian_code
(
  code
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT feide_gvs_guardian_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT feide_gvs_guardian_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*
 * Define relations between pupils and guardians(parents).
 */
category:main;
CREATE TABLE feide_gvs_guardian_pupil
(
  guardian_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_guardian_pupil_guardian_id
      REFERENCES person_info(person_id),

  pupil_id	NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_guardian_pupil_pupil_id
      REFERENCES person_info(person_id),

  relation	NUMERIC(6,0)
    NOT NULL
    CONSTRAINT feide_gvs_guardian_pupil_relation
      REFERENCES feide_gvs_guardian_code(code)
);


category:main;
CREATE TABLE feide_gvs_teacher_school
(
  teacher_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_teacher_school_teacher_id
      REFERENCES person_info(person_id),

  ou_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_teacher_school_scchool_id
      REFERENCES person_info(person_id)
);



category:main;
CREATE TABLE feide_gvs_program
(
  program_id
    NUMERIC(12,0)
    CONSTRAINT feide_gvs_program_pk PRIMARY KEY,

  class_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_program_class_id
      REFERENCES group_info(group_id),

  course_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT feide_gvs_program_course_id
      REFERENCES group_info(group_id),

  name
    CHAR VARYING(512)
    NOT NULL,

  teacher_id
    NUMERIC(12,0)
    CONSTRAINT feide_gvs_program_teacher_id
      REFERENCES person_info(person_id)
);


category:drop;
DROP TABLE feide_gvs_guardian_pupil;

category:drop;
DROP TABLE feide_gvs_guardian_code;

category:drop;
DROP TABLE feide_gvs_teacher_school;

category:drop;
DROP TABLE feide_gvs_program;
