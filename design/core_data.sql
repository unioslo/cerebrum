/*

Create entries for the core entity types.

TBD: Each of these statements should be done before the root table
     of the corresponding entity is created, so that it's possible to
     get the entity_type column check correct.  Or maybe this is
     better to fix later with an 'ALTER TABLE' statement?
*/
INSERT INTO [:table schema=cerebrum name=entity_type_code]
  (code, code_str, description) VALUES
  (2001, -- [:sequence schema=cerebrum name=code_seq op=next],
   'ou', 'Organizational Unit - see table "cerebrum.ou_info" and friends.');
INSERT INTO [:table schema=cerebrum name=entity_type_code]
  (code, code_str, description) VALUES
  (2002, -- [:sequence schema=cerebrum name=code_seq op=next],
   'person', 'Person - see table "cerebrum.person_info" and friends.');
INSERT INTO [:table schema=cerebrum name=entity_type_code]
  (code, code_str, description) VALUES
  (2003, -- [:sequence schema=cerebrum name=code_seq op=next],
   'account', 'User Account - see table "cerebrum.account_info" and friends.');
INSERT INTO [:table schema=cerebrum name=entity_type_code]
  (code, code_str, description) VALUES
  (2004, --[:sequence schema=cerebrum name=code_seq op=next],
   'group', 'Group - see table "cerebrum.group_info" and friends.');

INSERT INTO [:table schema=cerebrum name=contact_info_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'PHONE', 'Phone');
INSERT INTO [:table schema=cerebrum name=contact_info_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FAX', 'Fax');

INSERT INTO [:table schema=cerebrum name=address_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'POST',
   'Post address');
INSERT INTO [:table schema=cerebrum name=address_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'STREET',
   'Street address');

INSERT INTO [:table schema=cerebrum name=gender_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'F', 'Female');
INSERT INTO [:table schema=cerebrum name=gender_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'M', 'Male');

INSERT INTO [:table schema=cerebrum name=person_external_id_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'NO_BIRTHNO',
   'Norwegian birth number');

INSERT INTO [:table schema=cerebrum name=person_name_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FIRST', 'First name');
INSERT INTO [:table schema=cerebrum name=person_name_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LAST', 'Last name');
INSERT INTO [:table schema=cerebrum name=person_name_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FULL', 'Full name');

INSERT INTO [:table schema=cerebrum name=person_affiliation_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'EMPLOYEE',
   'Employed');

INSERT INTO [:table schema=cerebrum name=person_aff_status_code]
  (affiliation, status, status_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=current],
   [:sequence schema=cerebrum name=code_seq op=current],
   'VALID', 'Valid');

INSERT INTO [:table schema=cerebrum name=person_affiliation_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'STUDENT', 'Student');

INSERT INTO [:table schema=cerebrum name=person_aff_status_code]
  (affiliation, status, status_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=current],
   [:sequence schema=cerebrum name=code_seq op=current],
   'VALID', 'Valid');

INSERT INTO [:table schema=cerebrum name=account_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
   'P', 'Programvarekonto');

INSERT INTO [:table schema=cerebrum name=group_visibility_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'A', 'All');

INSERT INTO [:table schema=cerebrum name=group_membership_op_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'union',
   'Union');
INSERT INTO [:table schema=cerebrum name=group_membership_op_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'intersection',
   'Intersection');
INSERT INTO [:table schema=cerebrum name=group_membership_op_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'difference',
   'Difference');

INSERT INTO [:table schema=cerebrum name=posix_shell_code]
  (code, code_str, shell) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'bash', '/bin/bash');

INSERT INTO [:table schema=cerebrum name=value_domain_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'def_accname_dom',
   'Default domain for account names');

INSERT INTO [:table schema=cerebrum name=authentication_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'md5', 'MD5 password');

/*

***** Account som er laget av seg selv:

insert into entity_info values(888888, 2003);
INSERT INTO cerebrum.account_info (entity_type, account_id, owner_type,
            owner_id, np_type, create_date, creator_id, expire_date)
VALUES (2003, 888888, 2002, 2732, NULL, SYSDATE, 888888, SYSDATE);

***** En filgruppe i påvente av at det kommer på plass:

insert into entity_info values(999999, 2004);
insert into group_info (entity_type, group_id, description, visibility, 
  creator_id, create_date, expire_date ) 
VALUES (2004, 999999, 'test da vi ikke har gruppe ting enda', 19, 888888, SYSDATE, SYSDATE);

insert into posix_group values (999999, 0);

*/


/*
  UIO specific systems, will be moved to a separate file later
*/

INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');

INSERT INTO [:table schema=cerebrum name=ou_perspective_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO [:table schema=cerebrum name=ou_perspective_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');
