category:drop;
drop TABLE note;

category:code;
CREATE SEQUENCE note_seq;

category:main;
CREATE TABLE note
(
  note_id       NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_id_pk PRIMARY KEY,
                  DEFAULT
  create_date   TIMESTAMP
                  DEFAULT [:now]
                  NOT NULL,
  creator_id    NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_creator_id
                    REFERENCES account_info(account_id),
  entity_id     NUMERIC(12,0)
                  NOT NULL
                  CONSTRAINT note_entity_id
                    REFERENCES entity_info(entity_id),
  subject       CHAR VARYING(70),
  description   CHAR VARYING(1024)
);

