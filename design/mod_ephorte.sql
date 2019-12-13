/* encoding: utf-8
 *
 * Copyright 2007-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.no.uio.Ephorte
 */
category:metainfo;
name=ephorte;

category:metainfo;
version=1.2;

category:drop;
drop TABLE ephorte_role;
category:drop;
drop TABLE ephorte_role_type_code;
category:drop;
drop TABLE ephorte_arkivdel_code;
category:drop;
drop TABLE ephorte_journalenhet_code;
category:drop;
drop TABLE ephorte_permission;
category:drop;
drop TABLE ephorte_perm_type_code;


category:code;
CREATE TABLE ephorte_role_type_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT ephorte_role_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT ephorte_role_type_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE ephorte_arkivdel_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT ephorte_arkivdel_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT ephorte_arkivdel_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE ephorte_journalenhet_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT ephorte_journalenhet_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT ephorte_journalenhet_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


category:code;
CREATE TABLE ephorte_perm_type_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT ephorte_perm_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT ephorte_perm_type_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  ephorte_role
 *
 * This table defines roles that are granted to people in ePhorte.  It
 * basically defines the same fields as can be found in the
 * user-administrative interface in ePhorte.
*/
category:main;
CREATE TABLE ephorte_role
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT ephorte_role_person_id
      REFERENCES person_info(person_id),

  role_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT ephorte_role_type
      REFERENCES ephorte_role_type_code(code),

  standard_role
    CHAR(1)
    CONSTRAINT standard_rolle_bool_chk
      CHECK(standard_role IN ('T', 'F')),

  adm_enhet
    NUMERIC(12,0)
    CONSTRAINT ephorte_role_adm_enhet
      REFERENCES ou_info(ou_id),

  arkivdel
    NUMERIC(6,0)
    NULL
    CONSTRAINT ephorte_arkivdel
      REFERENCES ephorte_arkivdel_code(code),

  journalenhet
    NUMERIC(6,0)
    NULL
    CONSTRAINT ephorte_journalenhet
      REFERENCES ephorte_journalenhet_code(code),

  rolletittel
    CHAR VARYING(256),

  stilling
    CHAR VARYING(256),

  start_date
    DATE,

  end_date
    DATE,

  auto_role
    CHAR(1)
    CONSTRAINT auto_rolle_bool_chk
      CHECK(auto_role IN ('T', 'F')),

  UNIQUE (person_id, role_type, adm_enhet, arkivdel, journalenhet)
);


category:main;
CREATE TABLE ephorte_permission
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT ephorte_perm_person_id
      REFERENCES person_info(person_id),

  perm_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT ephorte_perm_type
      REFERENCES ephorte_perm_type_code(code),

  adm_enhet
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT ephorte_perm_adm_enhet
      REFERENCES ou_info(ou_id),

  requestee_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT ephorte_perm_requestee_id
      REFERENCES account_info(account_id),

  start_date
    DATE
    DEFAULT [:now]
    NOT NULL,

  end_date
    DATE,

  UNIQUE (person_id, perm_type, adm_enhet)
);
