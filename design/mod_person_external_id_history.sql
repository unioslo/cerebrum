/***
 *** Module 'person_external_id_history' -- keep track of the change
 *** history of persons' external IDs.
 ***/
CREATE TABLE person_external_id_change
(
  person_id	NUMERIC(12,0)
		CONSTRAINT person_external_id_change_person_id
		  REFERENCES person(person_id),
  id_type	CHAR VARYING(16)
		CONSTRAINT person_external_id_change_id_type
		  REFERENCES person_external_id_code(code),
  change_date	DATE
		NOT NULL,
  source_system CHAR VARYING(16)
		CONSTRAINT person_external_id_change_source_system
		  REFERENCES authoritative_system_code(code),
  old_id	CHAR VARYING(256)
		NOT NULL,
  new_id	CHAR VARYING(256)
		NOT NULL,
  CONSTRAINT person_external_id_change_pk PRIMARY KEY
    (person_id, id_type, change_date, source_system)
);
