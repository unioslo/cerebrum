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
 * Tables used by Cerebrum.modules.bofhd
 *
 * This is the table definition for the Cerebrum module BofhdAuth.
 *
 * For more information about the modules, see Cerebrum/modules/bofhd/auth.py.
 */
category:metainfo;
name=bofhd_auth;

category:metainfo;
version=1.2;


category:drop;
DROP TABLE auth_role;
category:drop;
DROP TABLE auth_op_target;
category:drop;
DROP TABLE auth_op_attrs;
category:drop;
DROP TABLE auth_operation;
category:drop;
DROP TABLE auth_operation_set;
category:drop;
DROP TABLE auth_op_code;


/*
 * The single operation code (constants).
 *
 * Each code represents a single operation that account may or not may be
 * permitted to do. Examples:
 * - set password
 * - create user on disk
 * - delete user from disk
 *
 * This table does not define how and where the operation is valid.
 *
 */
category:code;
CREATE TABLE auth_op_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT auth_op_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(64)
    NOT NULL
    CONSTRAINT auth_op_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*
 * The definition of an operation set (OpSet).
 *
 * It is the PK of the OpSet, and contains metadata about it. The collection of
 * operations that belong to the OpSet is defined in the `auth_operation` table.
 *
 * Examples on OpSets could be:
 * - "LocalIT" - containing standard operations that are needed for local IT to
 *   do their work, e.g. creating accounts.
 * - "StudenIT" - operations needed by Student IT, e.g. setting new password for
 *   students, i.e. accounts on student home disks.
     *
 */
category:main;
CREATE TABLE auth_operation_set
(
  op_set_id
    NUMERIC(12,0)
    CONSTRAINT auth_operation_set_pk PRIMARY KEY,

  name
    CHAR VARYING(30),

  description
    CHAR VARYING(512)
);


/*
 * Defines an operation within an OpSet.
 *
 * This defines what an OpSet consists of, e.g. that the OpSet "StudenIT" gives
 * access to the operation code "set_password". The operation might have certain
 * attributes related to it, which are put in the table `auth_op_attrs`.
 *
 */
category:main;
CREATE TABLE auth_operation
(
  op_id
    NUMERIC(12,0)
    CONSTRAINT auth_operation_pk PRIMARY KEY,

  op_code
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_operation_opcode_fk
      REFERENCES auth_op_code(code),

  op_set_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_operation_op_set_fk
      REFERENCES auth_operation_set(op_set_id)
);

category:main;
CREATE INDEX auth_operation_set_id ON auth_operation(op_set_id);


/*
 * Defines attributes associated with an operation inside an OpSet.
 *
 * The attributes could for instance set constraints on what the operation could
 * be used for.
 *
 * Some examples:
 * - The operation "spread_add" could have an attribute for what spread that is
 *   allowed to set. "LocalIT" might be allowed to give employee spread to AD,
 *   but they might not be allowed to set spread to Feide.
 * - The operation "grant_access" could have an attribute for allowed OpSets.
 *   "LocalIT" might be allowed to give employee access to modify groups, but
 *   they might not be allowed to grant access to Cert's privileges.
 * - Legal shells.
 *
 */
category:main;
CREATE TABLE auth_op_attrs
(
  op_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_op_attrs_fk
      REFERENCES auth_operation(op_id),

  attr
    CHAR VARYING(50)
);


/*
 * Defines what an auth role is targeting.
 *
 * A "target" is here defining _where_ the role is available. The target could
 * for instance point to a given disk, which means that the role gives access to
 * modify all the users that are put on the given disk (the OpSet the role
 * refers to decides of course what operations are available).
 *
 * The target also includes an attr element, which could contain more
 * restrictions to the target. This is for example used to give access to a
 * subset of disks on a given host.
 *
 * Note that this table is loosely coupled with the other tables. The element
 * entity_id is for instance not constrained to refer to an actual entity. This
 * is because this table is used a bit... flexible. It could for instance refer
 * to constants, like spreads, instead of real entities - this example makes you
 * able to target all entities which have a given spread.
 *
 * Examples:
 *
 *   Users on a disk:
 *     op_target_type = 'disk'     entity_id=<disk.entity_id>
 *   Users on a host:
 *     op_target_type = 'host'     entity_id=<host.entity_id>
 *   Users on a host:/path/host/sv-l*
 *     op_target_type = 'host'     entity_id=<host.entity_id>
 *     attr = 'sv-l.*' (note: regular expression, and only leaf directory)
 *   Allowed to set/clear spread X
 *     op_target_type = 'spread'   entity_id = <spread_code.code>
 *
 */
category:main;
CREATE TABLE auth_op_target
(
  op_target_id
    NUMERIC(12,0)
    CONSTRAINT auth_op_target_pk PRIMARY KEY,

  entity_id
    NUMERIC(12,0),

  target_type
    CHAR VARYING(16)
    NOT NULL,

  attr
    CHAR VARYING(50)
);

category:main;
CREATE INDEX auth_op_target_entity_id ON auth_op_target(entity_id);


/*
 * Roles
 *
 * A role associates an OpSet with a target, and affiliates this with an entity.
 * The entity is normally an account, or a group, which gives its group members
 * the role, indirectly.
 *
 */
category:main;
CREATE TABLE auth_role
(
  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_role_entity_fk
      REFERENCES entity_info(entity_id),

  op_set_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_role_op_set_fk
      REFERENCES auth_operation_set(op_set_id),

  op_target_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT auth_role_op_target_fk
      REFERENCES auth_op_target(op_target_id)
);

category:main;
CREATE INDEX auth_role_uid ON auth_role(entity_id, op_set_id, op_target_id);

category:main;
CREATE INDEX auth_role_eid ON auth_role(entity_id);

category:main;
CREATE INDEX auth_role_osid ON auth_role(op_set_id);

category:main;
CREATE INDEX auth_role_tid ON auth_role(op_target_id);
