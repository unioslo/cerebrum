/*
 * Copyright 2004-2005 University of Oslo, Norway
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
* Authorization commands performed in gro uses these tables wich are:
* - auth_func_map             Authorization function by spine type and method
* - auth_role                 Linking an operation set and a target with 
*                             a entity
* - auth_operation_set        A set of auth operations, like "own_user"
* - auth_operation            Linking codes and attrs with operation sets
* - auth_op_code              Operation codes like "set_password"
* - auth_op_attrs             Operation attrs used for validation
* - auth_op_target            Targets of the operation, entities, spreads
* - auth_op_target_type_code  Valid target types for auth_op_target
* - auth_op_target_attrs      Limiting the target, like ou=some_institute 
* - auth_op_target_attrs_key  Valid keys for auth_op_target_attrs given 
*                             auth_op_target target type 
*
* The user trying to perform a command is found as the entity_id in auth_role,
* either directly by his account_id or by any of his groups.
*
* The method called on a given Spine object will be matched by 
* auth_func_map - and the returned authorization functions
* will determine if the method call is allowed, by either:
* 
* 1) Special hard-coded rules
* 2) Looking up one or several auth_op_code directly, 
*    for instance set_unlimited_quota
* 3) Looking up the auth_op_code SpineType_method
*
* See comments below for more information.
*/
category:metainfo;
name=spine_auth;
category:metainfo;
version=1.0;


category:drop;
DROP TABLE auth_func_map;
category:drop;
DROP TABLE auth_role;
category:drop;
DROP TABLE auth_op_target_attrs;
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
category:drop;
DROP TABLE auth_op_target_attrs_key;
category:drop;
DROP TABLE auth_op_target_type_code;


/* Maps [object_type][.method] to authorization function
*   
* When authorization a method call, Spine will search this 
* mapping to find a valid match. The search will be done 
* something like this:
* 
*    for mapping sorted by descending priority:
*       if object_type matches the requested object
*             or is NULL:
*           if method matches the requested method
*                 or is NULL:
*             call auth_func_name  
*             if result is True or False:
*                 return result
*             else:
*                 continue    
*
* This means that each mapping function will be called if
* the object_type and method matches (or are NULL). The first function
* to return True (ACCEPT) or False (DROP) will take responsibility, 
* the search will stop, and the result will determine if the method call 
* will proceed or not.
*
* If the function returns None (RETURN), this indicates that the
* function did not take responsibility for this specific case (for
* instance a priority 0 handler for set_quarantine can return True or
* False on a specific quarantine value it is set to handle, but return
* None on all other quarantines). When a mapping matches, but the
* function handler does not take responsability, the search will
* continue - eventually matching a default handler. 
* 
* If no function mapping take responsability, the default action will be
* DENY.
*
* Users familiar with iptables/ipchains will recognize this
* ACCEPT/DROP/RETURN procedure.
*
*
* priority represents the importance of this mapping.
* The lower number, the earlier the auth_func_name will
* be called. Priority 0 is the highest priority.
* Recommendations:
* 
*     0   specific overrides for superadmins
*            (ie. *.set_quarantine for some quarantines)
*    10   general overrides for local admins
*            (ie. Account.*, *.get_quarantine(), ..)
*    30   specific type, specific method
*            (ie. Account.set_password)
*    50   specific type, all methods
*            (ie. Account.*) 
*    70   specific methods, all types
*            (ie. *.set_quarantine)
*   100   default for all types, all methods
*            (ie *.*)
*   
* object_type is the name of the Spine type to match, 
* for instance Account, Person, Spread. Note that this must be
* the direct name, as superclasses (ie. Entity)
* will not be searched. If object_type is NULL, this mapping
* will apply to any Spine types given the method.
*
* method is the name of the Spine method to match,
* for instance set_password, get_name, create_group.
* Note that the general Spine commands like create_group
* resides in the Spine type Commands. If method is
* NULL, this mapping will apply to any methods given
* the object_type.
* 
* If both object_type and method is NULL, the mapping will always match.
*
* auth_func_name is the name of the authorization function
* for Spine to call. 
* 
* The function will be called as 
* authfunc(operator, object, method, arguments) and must return either
* True, False or None, indicating ACCEPT (authorized), DROP (not
* authorized by rule) or RETURN (not authorized, but lower priority
* rules might authorize). 
* 
* Note that any other return values than None will be
* interpreted as True or False by their boolean value.
*
* FIXME: Name the (factory-compiled) class of authorization functions
*        and check the parameters
* 
*/
 category:main;
CREATE TABLE auth_func_map (
  auth_func_id      NUMERIC(6,0)
                        CONSTRAINT auth_func_map_pk PRIMARY KEY,
  priority          SMALLINT
                        NOT NULL,
  object_type       CHAR VARYING(128),
  method            CHAR VARYING(128),
  auth_func_name    CHAR VARYING(128)
                        NOT NULL
);


/* Defines the legal operations that may be performed.
*
* These codes will be used in two different ways:
*   a) Simple authorative "flags" used by 
*      one or several specific auth_funcs. 
*      For instance:
*           invite_members
*           remove_quarantine_teppe 
*      Such codes will have is_method=0

*   b) Used by a default auth_func handler to give permission for a
*      specific Spine method by their type and name.
*      For instance:
*           Group.add_member
*           Person.get_name
*           Account.set_password      
*      Such codes will have is_method=1
*             
*
* is_method set to true if code_str is objtype.method
* and this op_code is generated from the available
* Spine types and methods.
*/
category:code;
CREATE TABLE auth_op_code (
  code             NUMERIC(6,0)
                     CONSTRAINT auth_op_code_pk PRIMARY KEY,
  code_str         CHAR VARYING(256)
                     NOT NULL
                     CONSTRAINT auth_op_codestr_u UNIQUE,
  description      CHAR VARYING(512)
                     NOT NULL,
  is_method        BOOLEAN
                     NOT NULL
                     DEFAULT '0'
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
*  
*/
category:main;
CREATE TABLE auth_operation_set (
  op_set_id        NUMERIC(12,0)
                     CONSTRAINT auth_operation_set_pk PRIMARY KEY,
  name             CHAR VARYING(30) NOT NULL,
  description      CHAR VARYING(512)
                     NOT NULL DEFAULT '',
);


/* Contains a set of operations within an auth_operation_set.
*
* Links operation codes and operation attrs with operationsets.
*/
category:main;
CREATE TABLE auth_operation (
  op_id            NUMERIC(12,0)
                     CONSTRAINT auth_operation_pk PRIMARY KEY,
  op_code          NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_operation_opcode_fk
                       REFERENCES auth_op_code(code),
  op_set_id        NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_operation_op_set_fk
                       REFERENCES auth_operation_set(op_set_id)
);

category:main;
CREATE INDEX auth_operation_set_id ON auth_operation(op_set_id);


/* Defines attributes associated with an auth_operation.
* 
* Attributes can be used for validation,  such as legal shells etc.
*
* The specific meaning of a list of attributes associated with
* a auth_op_code is defined by the using auth_func.
* 
*/
category:main;
CREATE TABLE auth_op_attrs (
  op_id            NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_op_attrs_fk
                       REFERENCES auth_operation(op_id),
  attr             CHAR VARYING(50)
);


/*
* Possible auth_op_target target_types. 
* 
* The target type will usually be the same as
* the Spine type attached to the auth_op_target entity_id,
* for instance Account, Person, Spread.
* 
* Attached to a auth_op_target_type_code are also different
* auth_op_target_attrs_key that are valid keys for 
* this target_type in auth_op_target_attrs.
* 
*/
category:code;
CREATE TABLE auth_op_target_type_code (
  code             NUMERIC(6,0)
                     CONSTRAINT auth_op_target_type_code_pk PRIMARY KEY,
  code_str         CHAR VARYING(64)
                     NOT NULL
                     CONSTRAINT auth_op_target_type_codestr_u UNIQUE,
  description      CHAR VARYING(512)
                     NOT NULL
);


/* Defines rules for finding an entity target.
*
* The targets is the object the operation is performed on.
* 
* A target must be of a valid target_type, for instance
* auth_op_target_type_code('Group') or
* auth_op_target_type_code('Person').
*
* If entity_id is set, this target represents a 
* single entity. For instance, an account in auth_role.entity_id might
* have his own entity_id as a target for operations on his own user, 
* such as Account.set_password.
*
* If no entity_id is given, the rules of the auth_op_target_type_code
* applies for matching objects. 0 or more auth_op_target_attrs may
* be attached to the target limiting the search.
*
* For instance, an attribute 
* auth_op_target_attrs_key('spread')=spread_code('payroll')
* on an auth_op_target with
* target_type=auth_op_target_type_code('Account')
* will apply to accounts with the spread 'payroll'. 
*
*/
category:main;
CREATE TABLE auth_op_target (
  op_target_id     NUMERIC(12,0)
                     CONSTRAINT auth_op_target_pk PRIMARY KEY,
  entity_id        NUMERIC(12,0),
  target_type      NUMERIC(6,0)
                    NOT NULL
                    CONSTRAINT auth_op_target_type_fk
                        REFERENCES auth_op_target_type_code(code)
);

category:main;
CREATE INDEX auth_op_target_entity_id ON auth_op_target(entity_id);


/*
* A valid key for a auth_op_target_attrs key/value pair.
* 
* Each attribute in auth_op_target_attrs will normally
* limit the matching against objects.
* 
* Example keys:  spread, ou, affiliation_status 
*
* A auth_op_target_attrs_key is valid
* for a specific target_type. For instance,
* with target_type='Account' a valid key might
* be 'member_of' - indicating that the account
* must be member of the given group.
*
* The main use of target_type here is to 
* limit the view of possible keys for a 
* target_type in GUI interfaces. 
* 
* Note that several target_types might use the
* same key name, for instance "spread" might
* apply to both Groups and Accounts.
*
*/
category:main;
CREATE TABLE auth_op_target_attrs_key (
  key              CHAR VARYING(64)
                     NOT NULL,
  description      CHAR VARYING(512)
                     NOT NULL,
  target_type      NUMERIC(6,0)
                     NOT NULL
                     CONSTRAINT auth_op_target_attrs_key_target_type_fk
                        REFERENCES auth_op_target_type_code(code),
  CONSTRAINT auth_op_target_attrs_key_pk PRIMARY KEY (key, target_type)
);


/*
* A list of attributes attached to a auth_op_target
* in the form of key/value pairs. 
*
* Keys must be in auth_op_target_attrs_key.
* 
* The meaning of a value is specific to the
* combination of a target_type and key. 
* 
* For instance, with target_type=Account,
* the key "member_of" could mean that the  
* value is the group_id of a group the account
* must be a member of.
* 
* Or a more complicated example, i both "ou"
* and "affiliation" is given on a target_type=Person,
* the person must have the given affiliation_id to the
* given ou_id. 
*
* The exact interpretation is done by the code handling
* the given target_type.
* 
*/
category:main;
CREATE TABLE auth_op_target_attrs (
  op_target_id      NUMERIC(12,0)
                        NOT NULL
                        CONSTRAINT auth_op_target_attrs_op_target_id_fk
                            REFERENCES auth_op_target(op_target_id),
  key               CHAR VARYING(64)
                        NOT NULL
                        CONSTRAINT auth_op_target_attrs_key_fk
                            REFERENCES auth_op_target_attrs_key(key),
  value             CHAR VARYING(256)
                        NOT NULL,

  CONSTRAINT auth_op_target_attrs_pk PRIMARY KEY (op_target_id, key)
);


/* A role associates an auth_operation_set with an auth_op_target.
*
* Links the operating entity with a set of legal operations and a
* target.  The operation set contains several operations that are
* treated at the "same security level" for common targets. 
*
* For instance, normal users will have the operation set
* "Normal user" attached to their own account, allowing them
* to change their own password and login shell, plus viewing
* their own status.
* 
* Another example could be "Group administrator" giving permissions on a
* specific group for adding and removing members, updating the
* description, but not changing the name.
*
* Targets could also be general, as when auth_op_target.entity_id is
* NULL and filters are given by auth_op_target_attrs. This allows for
* instance the auth_operation_set "View other persons" on the
* target_type "Person" - allowing users to see limited attributes on
* other persons for finding their username, for instance First and Last
* name.
*
* The entity_id can be the direct entity_id of the operators account, or
* the entity_id of a group the operator is a member of. That way,
* general (mostly auto-generated) groups like "Students" can get general
* roles such as "View other persons".
*
*/
category:main;
CREATE TABLE auth_role (
  entity_id        NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_role_entity_fk
                       REFERENCES entity_info(entity_id),
  op_set_id        NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_role_op_set_fk
                       REFERENCES auth_operation_set(op_set_id),
  op_target_id     NUMERIC(12,0)
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

/* arch-tag: d2826091-c65a-4dfe-b5df-c63f9ec8041b
   (do not change this comment) */
