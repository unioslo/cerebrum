/***
 *** Module 'name-history' -- keep track of persons' names as they
 *** change over time.
 ***/
CREATE TABLE person_name_history
(
  person_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT person_name_history_person_id
		  REFERENCES person(person_id),
  name_variant	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_name_variant
		  REFERENCES person_name_code(code),
  source_system	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT person_name_history_source_system
		  REFERENCES authoritative_system_code(code),
  entry_date	DATE
		NOT NULL,
/* Must allow NULL names to indicate that a person have seized to have
   a value for one name_variant. */
  name		CHAR VARYING(256)
);

/* arch-tag: 429df112-847f-44d5-a8e9-5f10c9f64f9e
   (do not change this comment) */
