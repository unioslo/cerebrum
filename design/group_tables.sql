/* TBD:
 * Struktur for tildeling av ymse rettigheter til (IT-)grupper.
*/

/***********************************************************************
   Generalized group tables
 ***********************************************************************/


/*	group_info

  gname
	Name of the group.  Must be lowercase, but can contain (some)
	non-alphabetic characters.

  visibility
	Who should the name/contents of this list be visible to?

	TBD: Should group visibility rather be implemented as part of
	     the access delegation structure?

*/
CREATE TABLE group_info
(
  /* Dummy column, needed for type check against `entity_id'. */
  entity_type	CHAR VARYING(16)
		NOT NULL
		DEFAULT 'g'
		CONSTRAINT group_info_entity_type_chk
		  CHECK (entity_type = 'g'),

  group_id	NUMERIC(12,0)
		CONSTRAINT group_info_pk PRIMARY KEY,
  description	CHAR VARYING(512),
  visibility	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_info_visibility
		  REFERENCES group_visibility_code(code),
  creator_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_info_creator_id
		  REFERENCES account_info(account_id),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
/* expire_date kan brukes for å slette grupper, f.eks. ved at gruppen
   ikke lenger eksporteres etter at datoen er passert, men først
   slettes fra tabellen N måneder senere.  Det innebærer at man ikke
   får opprettet noen ny gruppe med samme navn før gruppa har vært
   borte fra eksporten i N måneder (med mindre man endrer på
   expire_date). */
  expire_date	DATE
		DEFAULT NULL,
  CONSTRAINT group_info_entity_id
    FOREIGN KEY (entity_type, group_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/* group_member:

  group_id
	Reference to the (super-)group this membership pertains to.

  operation

	Indicate whether this membership is a (set) 'U'nion,
	'I'ntersection or 'D'ifference.  When determining the members
	of a group, the member types are processed in this order:

	  Add all members from Union type members
	  Limit the member set using all Intersection type members
	  Reduce the member set by removing all Difference type members

 */
CREATE TABLE group_member
(
  group_id	NUMERIC(12,0)
		CONSTRAINT group_member_group_id
		  REFERENCES group_info(group_id),
  operation	CHAR VARYING(16)
		CONSTRAINT group_member_operation
		  REFERENCES group_membership_operation_code(code),
  member_type	CHAR VARYING(16)
		NOT NULL,
  member_id	NUMERIC(12,0),
  CONSTRAINT group_member_pk
    PRIMARY KEY (group_id, operation, member_id),
  CONSTRAINT group_member_exists
    FOREIGN KEY (member_type, member_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT group_member_not_self
    CHECK (group_id <> member_id)
);


/*

TBD: Er de følgende to tabellene nødvendige i det hele tatt, eller bør
     de erstattes med modul-spesifikke export-tabeller m/ tilhørende
     hooks?

In what fashions/to what systems can a group be exported?

This is split into the group type and, for lack of a better name, the
target system's "owner".  This means that the same code can easily be
used to perform an export for all exports with the same gtype
(e.g. the code to expand subgroups etc. for exporting as NIS
filegroups needs only be written once).

 */

CREATE TABLE group_export_type
(
  gtype		 CHAR VARYING(32),
  system_owner	 CHAR VARYING(32),
  description	 CHAR VARYING(512),
  PRIMARY KEY (gtype, system_owner) 
);



/* Define how a specific group should be exported. */
CREATE TABLE group_export
(
  gkey		NUMERIC(12,0)
		CONSTRAINT group_export_gkey REFERENCES group_info(group_id),
  gtype		CHAR VARYING(32),
  system_owner	CHAR VARYING(32),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL,
  create_by	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_export_create_by
		  REFERENCES account(account_id),
  delete_date	DATE
		DEFAULT NULL,
  delete_by	NUMERIC(12,0)
		DEFAULT NULL
		CONSTRAINT group_export_delete_by
		  REFERENCES account(account_id),
  CONSTRAINT group_export_pk PRIMARY KEY (gkey, gtype, system_owner),
  CONSTRAINT group_export_gtype FOREIGN KEY (gtype, system_owner)
    REFERENCES group_export_type(gtype, system_owner)
);


/* TBD: Må tenke mer på om spread skal skilles fra grupper, og
   evt. hvordan.  Skal spread være i kjernen i det hele tatt? */

/*
spread
(
  to_system
  entity_type
  user
  group
  person
  ...
  start_date
  end_date
);
*/

/* Bør man kunne override gruppenavn pr. system ved eksport?  Det vil tillate

   Internt i u2k	System X	System Y	System Z
   -------------------------------------------------------------
   A			A		foo		bar
   B			B		bar		foo
   C			C		C		A

, men *vil* vi egentlig det? */
