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

/* Defines the legal operations that may be performed, such as:
 - set password
 - create user on disk
 - delete user from disk */
category:code;
CREATE TABLE auth_op_code (
  code             NUMERIC(6,0)
                     CONSTRAINT auth_op_code_pk PRIMARY KEY,
  code_str         CHAR VARYING(16)
                     NOT NULL
                     CONSTRAINT auth_op_codestr_u UNIQUE,
  description      CHAR VARYING(512)
                   NOT NULL
);

/* PK for a collection of operations.*/

category:main;
CREATE TABLE auth_operation_set (
  op_set_id        NUMERIC(12,0)
                     CONSTRAINT auth_operation_set_pk PRIMARY KEY,
  name             CHAR VARYING(30)
);

/* Contains a set of operations within an auth_operation_set */
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
/* Defines attributes associated with an auth_operation, such as legal
   shells */

category:main;
CREATE TABLE auth_op_attrs (
  op_id            NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_op_attrs_fk
                       REFERENCES auth_operation(op_id),
  attr             CHAR VARYING(50)
);


/* Defines rules for finding an entity target. 

Examples:

  Users on a disk:
    op_target_type = 'disk' op_entity_id=<disk.entity_id>
  Users on a host:
    op_target_type = 'host' op_entity_id=<host.entity_id>
  Users on a host:/path/foo/sv-l*
    op_target_type = 'host' op_entity_id=<host.entity_id> 
    has_attrs=1, then fill auth_op_target_attrs with one or more regexps
*/

category:main;
CREATE TABLE auth_op_target (
  op_target_id     NUMERIC(12,0)
                     CONSTRAINT auth_op_target_pk PRIMARY KEY,
  entity_id        NUMERIC(12,0),
  target_type      CHAR VARYING(16),
  has_attr         NUMERIC(1,0) NOT NULL
);

/* Defines attributes associated with an op_target, such as a regexp for
   disk-name */

category:main;
CREATE TABLE auth_op_target_attrs (
  op_target_id     NUMERIC(12,0)
                     NOT NULL
                     CONSTRAINT auth_op_attrs_fk
                       REFERENCES auth_op_target(op_target_id),
  attr             CHAR VARYING(50)
);
category:main;
CREATE INDEX auth_op_target_attrs_oti ON auth_op_target_attrs(op_target_id);

/* A role associates an auth_operation_set with an auth_op_target */

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

