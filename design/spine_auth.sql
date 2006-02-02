/*
 * Copyright 2004-2006 University of Oslo, Norway
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

/* Tables used for authorization in Spine.
*
* Authorization commands performed in spine uses these tables wich are:
* - auth_operation             An operation is an method on a class
* - auth_operation_set         A set of auth operations
* - auth_operation_set_member  Linking operations in the set.
* - auth_target_entity         Privilege table for access to specific entities
* - auth_target_spread         Privilege table for access to spreads
* - auth_target_self           Privilege table for access to the user's own account, person, etc. 
* - auth_target_commands       Privilege table for access to commands without a specific entity.
*
* See comments below for more information.
*/
category:metainfo;
name=spine_auth;
category:metainfo;
version=1.0;


category:drop;
DROP TABLE auth_target_entity;
category:drop;
DROP TABLE auth_target_self;
category:drop;
DROP TABLE auth_target_spread;
category:drop;
DROP TABLE auth_target_commands;
category:drop;
DROP TABLE auth_target_all;
category:drop;
DROP TABLE auth_operation_set_member;
category:drop;
DROP TABLE auth_operation;
category:drop;
DROP TABLE auth_operation_set;
category:drop;
DROP SEQUENCE auth_;


category:main;
CREATE SEQUENCE auth_seq;

/* Defines the legal operations that may be performed.
* 
* 'op_class' is the class the method 'op_method' belongs to.
*/
category:main;
CREATE TABLE auth_operation (
  id            NUMERIC(12,0)
    CONSTRAINT auth_operation_pk PRIMARY KEY,
  op_class      CHAR VARYING(256)
    NOT NULL,
  op_method     CHAR VARYING(256)
    NOT NULL,
  CONSTRAINT auth_operation_u UNIQUE (op_class, op_method)
);

/* Collection of operations.
*
* An operation set contains several operations. You can only give 
* entities access to a set of operations.
*
* For instance, one auth_operation_set might be called
* 'Own account' and contain operations normally allowed
* for a user to do on his own account. (ie.
* auth_role.entity_id==auth_op_target.entity_id)
*
* Another example is an auth_operation_set of operations
* on other accounts.
*
* A set of operations can be used by several entities,
* and against several targets.
*/
category:main;
CREATE TABLE auth_operation_set (
  id            NUMERIC(12,0)
    CONSTRAINT auth_operation_set_pk PRIMARY KEY,
  name          CHAR VARYING(30)
    NOT NULL,
  description   CHAR VARYING(512)
    NOT NULL DEFAULT ''
);
category:main;
CREATE SEQUENCE auth_operation_set_id_seq;


/* Links operations in operations sets.
*/
category:main;
CREATE TABLE auth_operation_set_member (
  op_id         NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_operation_fk
      REFERENCES auth_operation(id),
  op_set_id     NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_operation_set_fk
      REFERENCES auth_operation_set(id),
  CONSTRAINT auth_operation_set_member_pk
    PRIMARY KEY (op_id, op_set_id)
);

/* Table for access to commands.
*
* The concept commads here refers to method on static classes,
* for example methods to create entities.
*/
category:main;
CREATE TABLE auth_target_commands (
  user_id       NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_commands_user_id_fk
      REFERENCES entity_info(entity_id),
  user_type     NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_commands_user_type_check
      CHECK (user_type IN ([:get_constant name=entity_account],
                [:get_constant name=entity_group])),
  op_set_id     NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_commands_op_set_fk
      REFERENCES auth_operation_set(id),
  CONSTRAINT auth_target_commands_user_check
    FOREIGN KEY (user_type, user_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* Table for access to self.
*
* Self can be information about the person which owns the user_id account, and
* other accounts the person owns. Check the implementation for full overview of
* what the concept self refers to.
*/
category:main;
CREATE TABLE auth_target_self (
  user_id       NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_self_user_id_fk
      REFERENCES entity_info(entity_id),
  user_type     NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_self_user_type_check
      CHECK (user_type IN ([:get_constant name=entity_account],
                [:get_constant name=entity_group])),
  op_set_id     NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_self_op_set_fk
      REFERENCES auth_operation_set(id),
  CONSTRAINT auth_target_self_user_check
    FOREIGN KEY (user_type, user_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* Table for access to members in a spread.
*/
category:main;
CREATE TABLE auth_target_spread (
  user_id       NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_spread_user_id_fk
      REFERENCES entity_info(entity_id),
  user_type     NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_spread_user_type_check
      CHECK (user_type IN ([:get_constant name=entity_account],
        [:get_constant name=entity_group])),
  op_set_id     NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_spread_op_set_fk
      REFERENCES auth_operation_set(id),
  spread        NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_spread_spread_fk
      REFERENCES spread_code(code),
  CONSTRAINT auth_target_spread_user_check
    FOREIGN KEY (user_type, user_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* Table for acess to specific entities.
*/
category:main;
CREATE TABLE auth_target_entity (
  user_id       NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_entity_user_id_fk
      REFERENCES entity_info(entity_id),
  user_type     NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_entity_user_type_check
      CHECK (user_type IN ([:get_constant name=entity_account],
        [:get_constant name=entity_group])),
  op_set_id     NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_entity_op_set_fk
      REFERENCES auth_operation_set(id),
  entity        NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_entity_entity_fk
      REFERENCES entity_info(entity_id),
  CONSTRAINT auth_target_entity_user_check
    FOREIGN KEY (user_type, user_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* Table with superusers.
*
* Target for users which should have access to operation-sets on all
* members of classes.
*/
category:main;
CREATE TABLE auth_target_all (
  user_id       NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_target_all_user_id_fk
      REFERENCES entity_info(entity_id),
  user_type     NUMERIC(6,0)
    NOT NULL
    CONSTRAINT auth_target_all_user_type_check
      CHECK (user_type IN ([:get_constant name=entity_account],
        [:get_constant name=entity_group])),
  CONSTRAINT auth_target_all_user_check
    FOREIGN KEY (user_type, user_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* arch-tag: d2826091-c65a-4dfe-b5df-c63f9ec8041b
   (do not change this comment) */
