/* encoding: utf-8
 *
 * Copyright 2010-2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.no.uio.voip
 */
category:metainfo;
name=voip;

category:metainfo;
version=1.0;


category:drop;
DROP TABLE entity_authentication_info ;

category:drop;
DROP TABLE entity_authentication_code ;

category:drop;
DROP TABLE voip_client;

category:drop;
DROP TABLE voip_address;

category:drop;
DROP TABLE voip_service;

category:drop;
DROP TABLE voip_service_type_code ;

category:drop;
DROP TABLE voip_client_type_code ;

category:drop;
DROP TABLE voip_client_info_code ;


/*
 * voip_client_info_code
 *
 * Define the phone device models that are allowed in voip.
 * (Hitachi ABC-12, Cisco XYZ-345, etc)
 */
category:code;
CREATE TABLE voip_client_info_code
(
  code
    NUMERIC(6, 0)
    CONSTRAINT voip_client_info_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(64)
    NOT NULL
    CONSTRAINT voip_client_info_code_unique UNIQUE,

  description
    CHAR VARYING(1024)
    NOT NULL
);


/*
 * voip_client_type_code
 *
 * Define possible client types ("softphone" and "hardphone" only for now)
 */
category:code;
CREATE TABLE voip_client_type_code
(
  code
    NUMERIC(6, 0)
    CONSTRAINT voip_client_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(64)
    NOT NULL
    CONSTRAINT voip_client_type_code_unique UNIQUE,

  description
    CHAR VARYING(256)
    NOT NULL
);


/*
 * voip_service_type_code
 *
 * Define possible kinds of non-personal voip phones (room, elevator, toilet,
 * etc)
 */
category:code;
CREATE TABLE voip_service_type_code
(
  code
    NUMERIC(6, 0)
    CONSTRAINT voip_service_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(64)
    NOT NULL
    CONSTRAINT voip_service_type_code_unique UNIQUE,

  description
    CHAR VARYING(256)
    NOT NULL
);


/*
 * voip_service
 *
 * This table describes what owns non-personal voip-addresses. A voip_address
 * is associated either to people or to a "non-person thingies". The
 * information about a "non-person thingy" is captured by this table.
 */
category:main;
CREATE TABLE voip_service
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_voip_service]
    NOT NULL
    CONSTRAINT voip_service_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_voip_service]),

  entity_id
    NUMERIC(12, 0)
    CONSTRAINT voip_service_pk PRIMARY KEY,

  description
    CHAR VARYING(256)
    NOT NULL,

  service_type
    NUMERIC(6, 0)
    NOT NULL
    CONSTRAINT voip_service_type_fk
      REFERENCES voip_service_type_code(code),

  ou_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT voip_service_ou_fk
      REFERENCES ou_info(ou_id),

  CONSTRAINT voip_service_is_of_proper_type_fk
    FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*
 * voip_address
 *
 */
category:main;
CREATE TABLE voip_address
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_voip_address]
    NOT NULL
    CONSTRAINT voip_address_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_voip_address]),

  entity_id
    NUMERIC(12, 0)
    CONSTRAINT voip_address_pk PRIMARY KEY,

  /*
   * FIXME: How do we enforce that owner_entity_id is either a voip_service
   *        or a person?
   */
  owner_entity_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT voip_address_owner_fk
      REFERENCES entity_info(entity_id),

  CONSTRAINT voip_address_is_of_proper_type_fk
    FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*
 * voip_client
 *
 * This table describes phone-related information in the module.
 *
 */
category:main;
CREATE TABLE voip_client
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_voip_client]
    NOT NULL
    CONSTRAINT voip_client_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_voip_client]),

  entity_id
    NUMERIC(12, 0)
    CONSTRAINT voip_client_pk PRIMARY KEY,

  voip_address_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT voip_client_to_address_fk
      REFERENCES voip_address(entity_id),

  client_type
    NUMERIC(6, 0)
    NOT NULL
    CONSTRAINT voip_client_type_fk
      REFERENCES voip_client_type_code(code),

  sip_enabled
    CHAR(1)
    DEFAULT 'T'
    NOT NULL
    CONSTRAINT voip_client_sip_enabled_bool
      CHECK (sip_enabled IN ('T', 'F')),

  /* FIXME: aa:bb:cc:dd:ee:ff is the only allowed syntax. How to enforce? */
  mac_address
    CHAR(17)
    NULL,

  CONSTRAINT voip_client_mac_check
    CHECK (
        (mac_address IS NULL AND
            client_type = [:get_constant name=voip_client_type_softphone])
        OR (mac_address IS NOT NULL AND
            client_type = [:get_constant name=voip_client_type_hardphone])
    ),

  client_info
    NUMERIC(6, 0)
    NOT NULL
    CONSTRAINT voip_client_client_info_fk
      REFERENCES voip_client_info_code(code),

  CONSTRAINT voip_client_is_of_proper_type_fk
    FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),

  CONSTRAINT voip_client_mac_address_is_unique
    UNIQUE (mac_address)
);


/* FIXME: Move this to mod_entity_authentication? */

/*
* entity_authentication_code
*
* Specifies the kind of authentication.
*
*/
category:code;
CREATE TABLE entity_authentication_code
(
  code
    NUMERIC(6, 0)
    CONSTRAINT entity_auth_code_pk
    PRIMARY KEY,

  code_str
    CHAR VARYING(256)
    NOT NULL
    CONSTRAINT entity_auth_code_unique UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*
* entity_authentication_info - authentication information for voip
*
* We keep track of authentication data for voip in this table (pin code,
* sipSecret, sipOldSecret).
*
*/
category:main;
CREATE TABLE entity_authentication_info
(
  entity_id
    NUMERIC(12, 0)
    NOT NULL
    CONSTRAINT entity_auth_info_fk
      REFERENCES entity_info(entity_id),

  auth_method
    NUMERIC(6, 0)
    NOT NULL
    CONSTRAINT entity_auth_info_method_fk
      REFERENCES entity_authentication_code(code),

  auth_data
    CHAR VARYING(4000)
    NOT NULL,

  CONSTRAINT entity_auth_info_pk
    PRIMARY KEY (entity_id, auth_method)
);
