/* The statements in this file should be executed under the Oracle
   user 'cerebrum'. */


/* REFERENCES kan i Oracle ikke grantes via en rolle.

   Dette betyr at moduler som definerer egne tabeller med
   REFERENCES-constraints mot kjernetabellene, må gjøre dette som en
   Oracle-bruker som _direkte_ har fått grantet REFERENCES på
   tabellen/kolonnen det skal refereres mot.

   Konsekvensen av dette er at det ser mer hårete ut enn først antatt
   å ha en Oracle-bruker pr. modul. */


/* Establish the Cerebrum role hierarchy. */

category:main;
CREATE ROLE read_code NOT IDENTIFIED;
category:main;
CREATE ROLE change_code NOT IDENTIFIED;
category:main;
GRANT read_code TO change_code;

category:main;
CREATE ROLE read_entity NOT IDENTIFIED;
category:main;
CREATE ROLE change_entity NOT IDENTIFIED;
category:main;
GRANT read_code, read_entity TO change_entity;
category:main;
CREATE ROLE read_ou NOT IDENTIFIED;
category:main;
CREATE ROLE change_ou NOT IDENTIFIED;
category:main;
GRANT read_code, read_ou TO change_ou;
category:main;
CREATE ROLE read_person NOT IDENTIFIED;
category:main;
CREATE ROLE change_person NOT IDENTIFIED;
category:main;
GRANT read_code, read_person TO change_person;
category:main;
CREATE ROLE read_account NOT IDENTIFIED;
category:main;
CREATE ROLE change_account NOT IDENTIFIED;
category:main;
GRANT read_code, read_account TO change_account;
category:main;
CREATE ROLE read_group NOT IDENTIFIED;
category:main;
CREATE ROLE change_group NOT IDENTIFIED;
category:main;
GRANT read_code, read_group TO change_group;

category:main;
CREATE ROLE read_core_table NOT IDENTIFIED;
category:main;
GRANT read_code, read_entity, read_ou, read_person, read_account,
      read_group
  TO read_core_table;

category:main;
CREATE ROLE change_core_table NOT IDENTIFIED;
category:main;
GRANT change_code, change_entity, change_ou, change_person,
      change_account, change_group
  TO change_core_table;


/* Grant object priviliges to roles. */

-- Code value tables:
category:main;
GRANT SELECT ON cerebrum.entity_type_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_type_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.authoritative_system_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.authoritative_system_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.country_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.country_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.language_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.language_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.value_domain_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.value_domain_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.address_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.address_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.contact_info_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.contact_info_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.quarantine_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.quarantine_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.ou_perspective_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.ou_perspective_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.gender_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.gender_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.person_external_id_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_external_id_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.person_name_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_name_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.person_affiliation_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_affiliation_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.person_aff_status_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_aff_status_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.account_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.account_code TO change_code;
category:main;
GRANT SELECT ON cerebrum.authentication_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.authentication_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.group_visibility_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.group_visibility_code
  TO change_code;
category:main;
GRANT SELECT ON cerebrum.group_membership_op_code TO read_code;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.group_membership_op_code
  TO change_code;

-- Entity tables
category:main;
GRANT SELECT ON cerebrum.entity_id_seq TO change_entity;
category:main;
GRANT SELECT ON cerebrum.entity_info TO read_entity;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_info TO change_entity;
category:main;
GRANT SELECT ON cerebrum.entity_name TO read_entity;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_name TO change_entity;
category:main;
GRANT SELECT ON cerebrum.entity_address TO read_entity;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_address
  TO change_entity;
category:main;
GRANT SELECT ON cerebrum.entity_contact_info TO read_entity;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_contact_info
  TO change_entity;
category:main;
GRANT SELECT ON cerebrum.entity_quarantine TO read_entity;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.entity_quarantine
  TO change_entity;

-- OU tables
category:main;
GRANT SELECT ON cerebrum.ou_info TO read_ou;
category:main;
GRANT INSERT, UPDATE, DELETE ON ou_info to change_ou;
category:main;
GRANT SELECT ON cerebrum.ou_structure TO read_ou;
category:main;
GRANT INSERT, UPDATE, DELETE ON ou_structure to change_ou;
category:main;
GRANT SELECT ON cerebrum.ou_name_language TO read_ou;
category:main;
GRANT INSERT, UPDATE, DELETE ON ou_name_language to change_ou;

-- Person tables
category:main;
GRANT SELECT ON cerebrum.person_info TO read_person;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_info TO change_person;
category:main;
GRANT SELECT ON cerebrum.person_external_id TO read_person;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_external_id
  TO change_person;
category:main;
GRANT SELECT ON cerebrum.person_name TO read_person;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_name TO change_person;
category:main;
GRANT SELECT ON cerebrum.person_affiliation TO read_person;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_affiliation
  TO change_person;
category:main;
GRANT SELECT ON cerebrum.person_affiliation_source TO read_person;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.person_affiliation_source
  TO change_person;

-- Account tables
category:main;
GRANT SELECT ON cerebrum.account_info TO read_account;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.account_info TO change_account;
category:main;
GRANT SELECT ON cerebrum.account_type TO read_account;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.account_type TO change_account;
category:main;
GRANT SELECT ON cerebrum.account_authentication TO read_account;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.account_authentication
  TO change_account;

-- Group tables
category:main;
GRANT SELECT ON cerebrum.group_info TO read_group;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.group_info TO change_group;
category:main;
GRANT SELECT ON cerebrum.group_member TO read_group;
category:main;
GRANT INSERT, UPDATE, DELETE ON cerebrum.group_member TO change_group;

-- Grant roles to users
category:main;
GRANT change_core_table TO cerebrum_user;


-- Module 'posix_user'
category:main;
CREATE ROLE read_mod_posix_user NOT IDENTIFIED;
category:main;
CREATE ROLE change_mod_posix_user NOT IDENTIFIED;
category:main;
GRANT read_mod_posix_user TO change_mod_posix_user;
category:main;
GRANT SELECT ON posix_shell_code TO read_mod_posix_user;
category:main;
GRANT SELECT ON posix_user TO read_mod_posix_user;
category:main;
GRANT SELECT ON posix_uid_seq TO read_mod_posix_user;
category:main;
GRANT SELECT ON posix_group TO read_mod_posix_user;
category:main;
GRANT SELECT ON posix_gid_seq TO read_mod_posix_user;
category:main;
GRANT INSERT, UPDATE, DELETE ON posix_shell_code TO read_mod_posix_user;
category:main;
GRANT INSERT, UPDATE, DELETE ON posix_user TO read_mod_posix_user;
category:main;
GRANT INSERT, UPDATE, DELETE ON posix_group TO read_mod_posix_user;

category:main;
GRANT read_mod_posix_user TO read_core_table;
category:main;
GRANT change_mod_posix_user TO change_core_table;


-- Module 'nis'
category:main;
CREATE ROLE read_mod_nis NOT IDENTIFIED;
category:main;
CREATE ROLE change_mod_nis NOT IDENTIFIED;
category:main;
GRANT SELECT ON nis_domain_code TO read_mod_nis;
category:main;
GRANT SELECT ON nis_netgroup TO read_mod_nis;
category:main;
GRANT INSERT, UPDATE, DELETE ON nis_domain_code TO read_mod_nis;
category:main;
GRANT INSERT, UPDATE, DELETE ON nis_netgroup TO read_mod_nis;

category:main;
GRANT read_mod_nis TO read_core_table;
category:main;
GRANT change_mod_nis TO change_core_table;


-- Module 'stedkode'
category:main;
CREATE ROLE read_mod_stedkode NOT IDENTIFIED;
category:main;
CREATE ROLE change_mod_stedkode NOT IDENTIFIED;
category:main;
GRANT read_mod_stedkode TO change_mod_stedkode;
category:main;
GRANT SELECT ON stedkode TO read_mod_stedkode;
category:main;
GRANT INSERT, UPDATE, DELETE ON stedkode TO change_mod_stedkode;

category:main;
GRANT read_mod_stedkode TO read_core_table;
category:main;
GRANT change_mod_stedkode TO change_core_table;



category:drop;
DROP ROLE change_mod_posix_user;
category:drop;
DROP ROLE read_mod_posix_user;
category:drop;
DROP ROLE change_mod_stedkode;
category:drop;
DROP ROLE read_mod_stedkode;
category:drop;
DROP ROLE change_mod_nis;
category:drop;
DROP ROLE read_mod_nis;
category:drop;
DROP ROLE change_core_table;
category:drop;
DROP ROLE read_core_table;
category:drop;
DROP ROLE change_group;
category:drop;
DROP ROLE read_group;
category:drop;
DROP ROLE change_account;
category:drop;
DROP ROLE read_account;
category:drop;
DROP ROLE change_person;
category:drop;
DROP ROLE read_person;
category:drop;
DROP ROLE change_ou;
category:drop;
DROP ROLE read_ou;
category:drop;
DROP ROLE change_entity;
category:drop;
DROP ROLE read_entity;
category:drop;
DROP ROLE change_code;
category:drop;
DROP ROLE read_code;
