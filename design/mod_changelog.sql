drop table change_type;
drop SEQUENCE change_log_seq;
drop TABLE change_log;

CREATE TABLE change_type
(
    change_type_id NUMERIC(6,0)
                   NOT NULL
                   CONSTRAINT change_type_pk PRIMARY KEY,
    category       CHAR VARYING(16),
    type           CHAR VARYING(16),
    msg_string     CHAR VARYING(60)
);



/* change_log

  tstamp
        Timestamp
  change_id
        Unique id
  subject_entity
        Entiy id which the operation is performed on
  subject_type
        The type of the subject entity
  change_type_id
        FK change_type
  dest_entity
        Entity id of destination
  change_params
        key-value mapping of arguments.
  change_by
        Entity id of changer iff it exists.
  change_program
        Name of program that performed the change when change_by is
        null
*/

CREATE SEQUENCE change_log_seq;
CREATE TABLE change_log
(
  tstamp          DATE
                  DEFAULT [:now]
                  NOT NULL,
  change_id       NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT change_id_pk PRIMARY KEY,
  subject_entity  NUMERIC(12,0),
  subject_type    CHAR VARYING(8),
  change_type_id  NUMERIC(6,0)
                  REFERENCES change_type(change_type_id),
  change_params   CHAR VARYING(255),
  change_by       NUMERIC(12,0)
                  REFERENCES entity_info(entity_id),
  change_program  CHAR VARYING(16),
  comment         CHAR VARYING(255)
);

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_group', 'add', 'added %%(subject)s to %%(dest)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_group', 'rem', 'removed %%(subject)s from %%(dest)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_group', 'create', 'created %%(subject)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_group', 'destroy', 'destroyed %%(subject)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_account', 'create', 'created %%(subject)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_account', 'def_fg', 'set %%(dest)s as default group for %%(subject)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_account', 'password', 'new password for %%(subject)s');

INSERT INTO [:table schema=cerebrum name=change_type]
  (change_type_id, category, type, msg_string) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
'e_account', 'move', '%%(subject)s moved to %%(param_name)s');
