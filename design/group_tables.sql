TBD:
 * Struktur for tildeling av ymse rettigheter til (IT-)grupper.

/***********************************************************************
   Generalized group tables
 ***********************************************************************/

group_visibility_code
(
  code		CHAR VARYING(16)
		CONSTRAINT group_visibility_code_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);

/*	group_info

  gname
	Name of the group.  Must be lowercase, but can contain (some)
	non-alphabetic characters.

  visibility
	Who should the name/contents of this list be visible to?

	TBD: Should group visibility rather be implemented as part of
	     the access delegation structure?

*/
CREATE SEQUENCE group_id;
CREATE TABLE group_info
(
  group_id	NUMERIC(12,0)
		CONSTRAINT group_info_pk PRIMARY KEY,
  gname		CHAR VARYING(256)
		NOT NULL
		CONSTRAINT group_info_gname_lc CHECK (gname = LOWER(gname)),
  description	CHAR VARYING(512),
  visibility	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_info_visibility
		  REFERENCES group_visibility_code(code),
  creator	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_info_creator REFERENCES account(account_id),
  create_date	DATE
		DEFAULT SYSDATE
		NOT NULL
/* created_by_system ? (kanskje nyttig for ad-hoc-grupper) */
/* expire_date ? */
);


CREATE TABLE group_membership_operation_code
(
  code		CHAR VARYING(16)
		CONSTRAINT group_membership_operation_pk PRIMARY KEY,
  description	CHAR VARYING(512)
		NOT NULL
);

/* group_member:

  group_id
	Reference to the (super-)group this membership pertains to.

  priority
	Determines the order of the various members of this
	(super-)group.

	TBD: When adding a member with a ordering between two previous
	     members, it would be nice if we didn't have to update the
	     ordering of any other members of the group; is there any
	     way to make that possible?

  operation

	Indicate whether this membership is a (set) 'U'nion,
	'I'ntersection or 'D'ifference.

	TBD: Is it really a good idea to allow the Intersection
	     operation for non-subgroup memberships?

 */
CREATE TABLE group_member
(
  group_id	NUMERIC(12,0)
		NOT NULL
		CONSTRAINT group_member_gkey REFERENCES group_info(group_id),
  priority	NUMERIC(9,0)
		NOT NULL,
  operation	CHAR VARYING(16)
		NOT NULL
		CONSTRAINT group_member_operation
		  REFERENCES group_membership_operation_code(code),
  person	NUMERIC(12,0)
		CONSTRAINT group_member_person
		  REFERENCES person(person_id),
  account	NUMERIC(12,0)
		CONSTRAINT group_member_account
		  REFERENCES account(account_id),
  subgroup	NUMERIC(12,0)
		CONSTRAINT group_member_subgroup
		  REFERENCES group_info(group_id),
/* ldap_dn  CHAR VARYING(256)
  DN må være "dc"-navngitt, jf RFC xxx. */
  CONSTRAINT group_member_pk PRIMARY KEY (group_id, priority),
  CONSTRAINT group_member_onetype CHECK
    (DECODE(NVL(person, 'NO SUCH PERSON'), 'NO SUCH PERSON', 0, 1)
   + DECODE(NVL(account, 'NO SUCH ACCOUNT'), 'NO SUCH ACCOUNT', 0, 1)
   + DECODE(NVL(subgroup, 'NO SUCH GROUP'), 'NO SUCH GROUP', 0, 1)
   = 1),
  CONSTRAINT group_member_subgroup_not_self CHECK (NVL(subgroup, '?') <> gkey)
);


/*

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



/***********************************************************************
   NIS module
 ***********************************************************************/

/*

Extra information for groups exported as NIS filegroups.

Note that the names of NIS filegroups can't be longer than 8
character; if a group with too long a name is referenced in this
table, it should be ignored by the export machinery.

   gid
	Unix numeric filegroup ID.
 */
CREATE TABLE nis_filegroup
(
  gkey		NUMERIC(12,0)
		CONSTRAINT nis_filegroup_pk PRIMARY KEY
		CONSTRAINT nis_filegroup_gkey REFERENCES group_info(group_id),
  gid		NUMERIC(5,0)
		CONSTRAINT nis_filegroup_gid UNIQUE
);


/* TBD: Må tenke mer på om spread skal skilles fra grupper, og
   evt. hvordan.  Skal spread være i kjernen i det hele tatt? */

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


/* Bør man kunne override gruppenavn pr. system ved eksport?  Det vil tillate

   Internt i u2k	System X	System Y	System Z
   -------------------------------------------------------------
   A			A		foo		bar
   B			B		bar		foo
   C			C		C		A

, men *vil* vi egentlig det? */
