category:metainfo;
name=changelog;
category:metainfo;
version=1.0;
category:drop;
drop TABLE change_handler_data;
category:drop;
drop TABLE change_log;
category:drop;
drop table change_type;
category:drop;
drop SEQUENCE change_log_seq;

category:code;
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

category:code;
CREATE SEQUENCE change_log_seq;
category:main;
CREATE TABLE change_log
(
  tstamp          TIMESTAMP
                  DEFAULT [:now]
                  NOT NULL,
  change_id       NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT change_id_pk PRIMARY KEY,
  subject_entity  NUMERIC(12,0),
  change_type_id  NUMERIC(6,0)
                  REFERENCES change_type(change_type_id),
  dest_entity     NUMERIC(12,0),
  change_params   CHAR VARYING(255),
  change_by       NUMERIC(12,0)
                  REFERENCES entity_info(entity_id),
  change_program  CHAR VARYING(16),
  description     CHAR VARYING(255)
);

category:main;
create index change_log_subject_idx on change_log(subject_entity);

/* Store first and last change_id that a CLHandler client has
received.  Multiple entries for one evthdlr_key are legal and
indicates holes in the sequence.
*/
category:main;
CREATE TABLE change_handler_data
(
  evthdlr_key    CHAR VARYING(20) NOT NULL, 
  first_id       NUMERIC(12,0) NOT NULL,
  last_id        NUMERIC(12,0) NOT NULL
);

/* arch-tag: 36e9a720-cbcf-441e-9b2e-76b53deb979d
   (do not change this comment) */
