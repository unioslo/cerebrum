category:drop;
DROP TABLE dns_srv_record;
category:drop;
DROP TABLE dns_override_reversemap;
category:drop;
DROP TABLE dns_general_dns_record;
category:drop;
DROP TABLE dns_field_type_code;
category:drop;
DROP TABLE dns_cname_record;
category:drop;
DROP TABLE dns_host_info;
category:drop;
DROP TABLE dns_a_record;
category:drop;
DROP TABLE dns_ip_number;
category:drop;
DROP TABLE dns_mx_set_member;
category:drop;
ALTER TABLE dns_owner DROP CONSTRAINT dns_owner_mx_set_fk;
category:drop;
DROP TABLE dns_mx_set;
category:drop;
DROP TABLE dns_owner;
category:drop;
DROP TABLE dns_hinfo_code;
category:drop;
DROP TABLE dns_entity_note;
category:drop;
DROP TABLE dns_entity_note_code;
category:drop;
DROP SEQUENCE ip_number_id_seq;

/* Stores an ip_number
   ip_number_id: identifier
   a_ip:    textual representation of the ip-number
   aaaa_ip: ip (v6) address
   ipnr:    the numerical 32-bit ip-number.

   We store a_ip to make searches easier, and ipnr to make searches
   based on ranges of ips easier. 
*/
category:main;
CREATE SEQUENCE ip_number_id_seq;
category:main;
CREATE TABLE dns_ip_number (
  ip_number_id  NUMERIC(12,0)
                  CONSTRAINT ip_number_pk PRIMARY KEY,
  a_ip          CHAR VARYING(30) NOT NULL
                CONSTRAINT ip_number_a_ip_u UNIQUE,
  aaaa_ip       CHAR VARYING(30),
  ipnr          NUMERIC(14,0) NOT NULL
);

/* Stores a dns_owner

     zone:          TODO - for multiple zones (affects name unique constr.)
     dns_owner_id:  identifier
     entity_type:   dns_owner
     name:          name of this dns-owner
     is_foreign:    if this owner is not in uio.no (may be dropped later)
     mx_set_id:     FK to mx_set

   The name is stored in entity_name.  By making it an entity,
   netgroups becomes trivial.
*/
category:main;
CREATE TABLE dns_owner (
  dns_owner_id  NUMERIC(12,0)
                  CONSTRAINT dns_owner_pk PRIMARY KEY,
  entity_type   NUMERIC(6,0)
                DEFAULT [:get_constant name=entity_dns_owner]
                NOT NULL
                CONSTRAINT a_record_entity_type_chk
                  CHECK (entity_type = [:get_constant name=entity_dns_owner]),
  name          CHAR VARYING(256) NOT NULL
                CONSTRAINT dns_owner_name_u UNIQUE,
  is_foreign    NUMERIC(1,0) NOT NULL
                CONSTRAINT dns_owner_is_foreign_bool
		  CHECK (is_foreign IN (0, 1)),
  mx_set_id     NUMERIC(12,0),
  CONSTRAINT dns_owner_entity_id
    FOREIGN KEY (entity_type, dns_owner_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/* Stores an a_record that maps between a hostname and an IP.

   entity_type: part of FK
   a_record_id: identifier
   dns_owner_id: FK to dns_owner
   ip_number_id: FK to ip_number
   ttl:     optional TTL value 
   mac:     mac address

   it is an entity so that we may register entity_note
   (comment/contact) for it.
*/

category:main;
CREATE TABLE dns_a_record (
  entity_type   NUMERIC(6,0)
                DEFAULT [:get_constant name=entity_dns_a_record]
                NOT NULL
                CONSTRAINT a_record_entity_type_chk
                  CHECK (entity_type = [:get_constant name=entity_dns_a_record]),
  a_record_id   NUMERIC(12,0)
                  CONSTRAINT a_record_pk PRIMARY KEY,
  dns_owner_id  NUMERIC(12,0)
                  CONSTRAINT a_record_owner_fk 
                  REFERENCES dns_owner(dns_owner_id),
  ip_number_id  NUMERIC(12,0)
                  CONSTRAINT a_record_ip_fk 
                  REFERENCES dns_ip_number(ip_number_id),
  ttl           NUMERIC(6,0), 
  mac           CHAR VARYING(128),
  CONSTRAINT a_record_ip_owner_u
    UNIQUE (ip_number_id, dns_owner_id)
);

/* Defines legal HINFO values
*/

category:code;
CREATE TABLE dns_hinfo_code
(
  code          NUMERIC(6,0)
                CONSTRAINT hinfo_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT hinfo_codestr_u UNIQUE,
  cpu           CHAR VARYING(64) NOT NULL,
  os            CHAR VARYING(64) NOT NULL
);

/* Store information about a host (name-clash with existing table
   host_info).  A host is typically a hardware box.

   entity_type:  part of FK 
   host_id:      identifier    
   dns_owner_id: FK to dns_owner
   ttl:          optional TTL value          
   hinfo:        FK to hinfo_code
                
   it is an entity so that we may register entity_note
   (comment/contact) for it.
*/

category:main;
CREATE TABLE dns_host_info(
  entity_type   NUMERIC(6,0)
                DEFAULT [:get_constant name=entity_dns_host]
                NOT NULL
                CONSTRAINT dns_host_info_entity_type_chk
                  CHECK (entity_type = [:get_constant name=entity_dns_host]),
  host_id       NUMERIC(12,0)
                CONSTRAINT dns_host_info_pk PRIMARY KEY,
  dns_owner_id  NUMERIC(12,0) NOT NULL
                  CONSTRAINT host_info_owner_fk 
                  REFERENCES dns_owner(dns_owner_id)
                CONSTRAINT dns_host_info_dns_owner_id_u UNIQUE,
  ttl           NUMERIC(6,0), 
  hinfo         NUMERIC(6,0) NOT NULL
                  CONSTRAINT hinfo_code
                  REFERENCES dns_hinfo_code(code),
  CONSTRAINT dns_host_info_entity_id
    FOREIGN KEY (entity_type, host_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/* Defines a mx_set.  mx_set is used to represent a collection of mx
   targets for a host.  The number of sets is typically small.

   mx_set_id:  PK
   name:       used in clients to identify the set

*/

category:main;
CREATE TABLE dns_mx_set (         
  mx_set_id     NUMERIC(12,0)
                   CONSTRAINT mx_set_pk
                   PRIMARY KEY,
  name          CHAR VARYING(64) NOT NULL
                  CONSTRAINT mx_set_name_u UNIQUE
);

/* Delayed constraint due to circular dependency */
category:main;
ALTER TABLE dns_owner
    ADD CONSTRAINT dns_owner_mx_set_fk 
    FOREIGN KEY (mx_set_id) 
    REFERENCES dns_mx_set(mx_set_id);

/* Defines members of a mx_set.

   mx_set_id:  FK to mx_set
   ttl:        optional TTL value      
   pri:        priority         
   target_id:  FK to dns_owner
                
   The host that has an MX record is usually an A record, while the
   target is usually a host.  We don't enforce this as there are
   exceptions.
*/

category:main;
CREATE TABLE dns_mx_set_member (         
  mx_set_id     NUMERIC(12,0)
                   CONSTRAINT mx_set_fk
                   REFERENCES dns_mx_set(mx_set_id),
  ttl              NUMERIC(6,0), 
  pri            NUMERIC(3,0) NOT NULL,
  target_id      NUMERIC(12,0)
                   CONSTRAINT mx_set_target_fk
                   REFERENCES dns_owner(dns_owner_id)
);

/* Store cnames for an a_record.

   entity_type:     part of FK       
   cname_id:        identifier          
   cname_owner_id:  FK to dns_owner    
   ttl:             optional TTL value          
   target_owner_id: FK to dns_owner   

   it is an entity so that one may attach entity_note to it. */

category:main;
CREATE TABLE dns_cname_record(
  entity_type       NUMERIC(6,0)
                    DEFAULT [:get_constant name=entity_dns_cname]
                    NOT NULL
                    CONSTRAINT cname_record_entity_type_chk
                      CHECK (entity_type = [:get_constant name=entity_dns_cname]),
  cname_id          NUMERIC(12,0)
                      CONSTRAINT cname_record_pk PRIMARY KEY,
  cname_owner_id    NUMERIC(12,0)
                      CONSTRAINT cname_record_owner_fk
                      REFERENCES dns_owner(dns_owner_id),
  ttl               NUMERIC(6,0),
  target_owner_id   NUMERIC(12,0)
                      CONSTRAINT cname_record_target_fk
                      REFERENCES dns_owner(dns_owner_id),
  CONSTRAINT cname_record_entity_id
    FOREIGN KEY (entity_type, cname_id)
    REFERENCES entity_info(entity_type, entity_id)

);

/* Defines the legal field types for the general_dns_record.  Typical
   values are TXT, RP */

category:code;
CREATE TABLE dns_field_type_code
(
  code          NUMERIC(6,0)
                CONSTRAINT field_type_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT field_type_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

/* A general record that has some data and an optional TTL associated
   with a dns-owner.  TXT records is one example.
 */

category:main;
CREATE TABLE dns_general_dns_record(
  dns_owner_id    NUMERIC(12,0)
                    CONSTRAINT a_record_owner_fk 
                    REFERENCES dns_owner(dns_owner_id),
  field_type      NUMERIC(6,0) NOT NULL
                    CONSTRAINT field_type_code_fk
                  REFERENCES dns_field_type_code(code),
  ttl             NUMERIC(6,0), 
  data            CHAR VARYING(128) NOT NULL,
  CONSTRAINT general_dns_record_pk PRIMARY KEY (dns_owner_id, field_type)
);

/* Default is that the reversemap can be automatically deduced from
   a_record.  This table stores overrides to this behaviour.  

   ext_name/ext_ip is filled when the a_record references won't be
   unique or don't exist.
  */

category:main;
CREATE TABLE dns_override_reversemap(
  ip_number_id  NUMERIC(12,0)
                  CONSTRAINT override_reversemap_ip_fk 
                  REFERENCES dns_ip_number(ip_number_id),
  dns_owner_id  NUMERIC(12,0)
                  CONSTRAINT override_reversemap_owner_fk 
                  REFERENCES dns_owner(dns_owner_id),
  CONSTRAINT override_reversemap_unique UNIQUE (ip_number_id)
);

/* Stores a SRV (service) record (RFC 2782)

  It seems that the PK should span all-rows except ttl

  Example of this record type:
    <service> <ttl> SRV <priority> <weight> <port> <hostname>
    _http._tcp.example.com. SRV 10 5 80. www.example.com

*/

category:main;
CREATE TABLE dns_srv_record (
  service_owner_id NUMERIC(12,0)
                     CONSTRAINT srv_record_service_owner_fk
                     REFERENCES dns_owner(dns_owner_id),
  pri              NUMERIC(3,0) NOT NULL,
  weight           NUMERIC(3,0) NOT NULL,
  port             NUMERIC(5,0) NOT NULL,
  ttl              NUMERIC(6,0), 
  target_owner_id  NUMERIC(12,0)
                      CONSTRAINT srv_record_target_owner_fk
                      REFERENCES dns_owner(dns_owner_id)
);

/* Contains hostnames that are illegal to use.  Will progbably not be
   used.  */
/*
category:main;
CREATE TABLE dns_reserved_host(
  id              CHAR VARYING(128)
);
*/
/* Defines the legal field types for the general_dns_record.  Typical
   values are TXT, RP */

category:code;
CREATE TABLE dns_entity_note_code
(
  code          NUMERIC(6,0)
                CONSTRAINT entity_note_code_pk PRIMARY KEY,
  code_str      CHAR VARYING(16)
                NOT NULL
                CONSTRAINT entity_note_codestr_u UNIQUE,
  description   CHAR VARYING(512)
                NOT NULL
);

/* A general record with some info about an entity where we only want
   one instance of the information of a given type. */

category:main;
CREATE TABLE dns_entity_note(
  entity_id       NUMERIC(12,0)
                    CONSTRAINT entity_note_fk 
                    REFERENCES entity_info(entity_id),
  note_type       NUMERIC(6,0) NOT NULL
                    CONSTRAINT entity_note_code_fk
                  REFERENCES dns_entity_note_code(code),
  data            CHAR VARYING(128) NOT NULL,
  CONSTRAINT entity_note_pk PRIMARY KEY (entity_id, note_type)
);

/* arch-tag: 712a00e6-bdbe-4029-9dcc-795f9a047ee8
   (do not change this comment) */
