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
INSERT INTO [:table schema=cerebrum name=contact_info_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'EMAIL', 'Email');

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
INSERT INTO [:table schema=cerebrum name=gender_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'X', 'Unknown');

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

/* It is rather likely that some installations want the names of their
   user accounts to live in the same value domain as the names of
   their groups.  Such a setup is not possible with the following two
   statements -- the second one will fail due to uniqueness constraints.
   Hence, we need to come up with a better solution... */
INSERT INTO [:table schema=cerebrum name=value_domain_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
   [:get_config var=DEFAULT_GROUP_NAMESPACE],
   'Default domain for group names');
INSERT INTO [:table schema=cerebrum name=value_domain_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next],
   [:get_config var=DEFAULT_ACCOUNT_NAMESPACE],
   'Default domain for account names');

INSERT INTO [:table schema=cerebrum name=authentication_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'md5', 'MD5 password');

INSERT INTO [:table schema=cerebrum name=authentication_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'crypt', 'crypt(3) password');

/*
  UIO specific systems, will be moved to a separate file later
*/

INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');
INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'Manual', 'Manual registration');
INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'Ureg', 'Imported from ureg');

INSERT INTO [:table schema=cerebrum name=ou_perspective_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO [:table schema=cerebrum name=ou_perspective_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');

INSERT INTO [:table schema=cerebrum name=authoritative_system_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'SATS', 'SATS');

INSERT INTO [:table schema=cerebrum name=person_external_id_code]
  (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'SATS_PERSONOID',
   'PK in SATS');
