INSERT INTO entity_type_code (code, code_str, description) VALUES
  (2001, 'o', 'Organizational Unit - see table "cerebrum.ou_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (2002, 'p', 'Person - see table "cerebrum.person_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (2003, 'a', 'User Account - see table "cerebrum.account_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (2004, 'g', 'Group - see table "cerebrum.group_info" and friends.');

INSERT INTO contact_info_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'PHONE', 'Phone');
INSERT INTO contact_info_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FAX', 'Fax');

INSERT INTO address_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'POST', 'Post address');
INSERT INTO address_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'STREET', 'Street address');

INSERT INTO gender_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'F', 'Female');
INSERT INTO gender_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'M', 'Male');

INSERT INTO person_external_id_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'NO_BIRTHNO', 'Norwegian birth number');

INSERT INTO person_name_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FIRST', 'First name');
INSERT INTO person_name_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LAST', 'Last name');
INSERT INTO person_name_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FULL', 'Full name');

INSERT INTO person_affiliation_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'EMPLOYEE', 'Employed');

INSERT INTO person_aff_status_code (affiliation, status, status_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=current], [:sequence schema=cerebrum name=code_seq op=current], 'VALID', 'Valid');

INSERT INTO person_affiliation_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'STUDENT', 'Student');

INSERT INTO person_aff_status_code (affiliation, status, status_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=current], [:sequence schema=cerebrum name=code_seq op=current], 'VALID', 'Valid');

/*
  UIO specific systems, will be moved to a separate file later
*/

INSERT INTO authoritative_system_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO authoritative_system_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');

INSERT INTO ou_perspective_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'LT', 'LT');
INSERT INTO ou_perspective_code (code, code_str, description) VALUES
  ([:sequence schema=cerebrum name=code_seq op=next], 'FS', 'FS');
