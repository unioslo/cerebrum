INSERT INTO entity_type_code (code, code_str, description) VALUES
  (code_seq.nextval, 'o', 'Organizational Unit - see table "cerebrum.ou_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (code_seq.nextval, 'p', 'Person - see table "cerebrum.person_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (code_seq.nextval, 'a', 'User Account - see table "cerebrum.account_info" and friends.');
INSERT INTO entity_type_code (code, code_str, description) VALUES
  (code_seq.nextval, 'g', 'Group - see table "cerebrum.group_info" and friends.');

INSERT INTO contact_info_code (code, code_str, description) VALUES
  (code_seq.nextval, 'PHONE', 'Phone');
INSERT INTO contact_info_code (code, code_str, description) VALUES
  (code_seq.nextval, 'FAX', 'Fax');

INSERT INTO address_code (code, code_str, description) VALUES
  (code_seq.nextval, 'POST', 'Post address');
INSERT INTO address_code (code, code_str, description) VALUES
  (code_seq.nextval, 'STREET', 'Street address');

INSERT INTO gender_code (code, code_str, description) VALUES
  (code_seq.nextval, 'F', 'Female');
INSERT INTO gender_code (code, code_str, description) VALUES
  (code_seq.nextval, 'M', 'Male');

INSERT INTO person_external_id_code (code, code_str, description) VALUES
  (code_seq.nextval, 'NO_BIRTHNO', 'Norwegian birth number');

INSERT INTO person_name_code (code, code_str, description) VALUES
  (code_seq.nextval, 'FIRST', 'First name');
INSERT INTO person_name_code (code, code_str, description) VALUES
  (code_seq.nextval, 'LAST', 'Last name');
INSERT INTO person_name_code (code, code_str, description) VALUES
  (code_seq.nextval, 'FULL', 'Full name');

INSERT INTO person_affiliation_code (code, code_str, description) VALUES
  (code_seq.nextval, 'EMPLOYEE', 'Employed');

INSERT INTO person_affiliation_code (code, code_str, description) VALUES
  (code_seq.nextval, 'STUDENT', 'Student');

INSERT INTO person_aff_status_code (affiliation, status, status_str, description) VALUES
  (code_seq.currval, code_seq.currval, 'VALID', 'Valid');

/*
  UIO specific systems, will be moved to a separate file later
*/

INSERT INTO authoritative_system_code (code, code_str, description) VALUES
  (code_seq.nextval, 'LT', 'LT');
INSERT INTO authoritative_system_code (code, code_str, description) VALUES
  (code_seq.nextval, 'FS', 'FS');

INSERT INTO ou_perspective_code (code, code_str, description) VALUES
  (code_seq.nextval, 'LT', 'LT');

commit;
