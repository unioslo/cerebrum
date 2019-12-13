/* encoding: utf-8
 *
 * Copyright 2005-2019 University of Oslo, Norway
 *
 * This file is part of Cerebrum.
 *
 * Cerebrum is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * Cerebrum is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Cerebrum; if not, write to the Free Software Foundation,
 * Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
 *
 *
 * Tables used by Cerebrum.modules.dns
 */
category:metainfo;
name=dns;

category:metainfo;
version=1.5;

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
DROP TABLE dns_zone;
category:drop;
DROP TABLE dns_entity_note;
category:drop;
DROP TABLE dns_entity_note_code;
category:drop;
DROP TABLE dns_subnet;
category:drop;
DROP TABLE dns_ipv6_subnet;
category:drop;
DROP SEQUENCE ip_number_id_seq;

category:main;
CREATE SEQUENCE ip_number_id_seq;


/*  dns_ip_number
 *
 * The ``dns_ip_number`` table stores an ip_number.  We store ip-numbers
 * in a separate table to make unique-constaint and consistent updates to
 * dns_a_record and dns_override_reversemap easier.  It has the following
 * columns::
 *
 *    ip_number_id  identifier (PK)
 *    a_ip          textual representation of the ip-number
 *    aaaa_ip       ip (v6) address
 *    ipnr          the numerical 32-bit ip-number.
 *
 * We store a_ip to make searches easier, and ipnr to make searches
 * based on ranges of ips easier.
 */
category:main;
CREATE TABLE dns_ip_number
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_ip_number]
    NOT NULL
    CONSTRAINT dns_ip_number_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_ip_number]),

  ip_number_id
    NUMERIC(12,0)
    CONSTRAINT ip_number_pk PRIMARY KEY,

  a_ip
    CHAR VARYING(30) NOT NULL
    CONSTRAINT ip_number_a_ip_u UNIQUE,

  aaaa_ip
    CHAR VARYING(30),

  ipnr
    NUMERIC(14,0) NOT NULL,

  mac_adr
    CHAR VARYING(30) DEFAULT NULL,

  CONSTRAINT dns_ip_number_entity_id
    FOREIGN KEY (entity_type, ip_number_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_ipv6_number
 *
 * The ``dns_ipv6_number`` table stores an IPv6_number.  We store IPv6-numbers
 * in a separate table to make unique-constaint and consistent updates to
 * dns_aaaa_record and dns_override_reversemap_ipv6 easier.  It has the following
 * columns:
 *
 *   ipv6_number_id  identifier (PK)
 *   aaaa_ip       ip (v6) address
 *   mac_adr       MAC address
 */
category:main;
CREATE TABLE dns_ipv6_number
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_ipv6_number]
    NOT NULL
    CONSTRAINT dns_ipv6_number_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_ipv6_number]),

  ipv6_number_id
    NUMERIC(12,0)
    CONSTRAINT ipv6_number_pk PRIMARY KEY,

  aaaa_ip
    CHAR VARYING(39)
    CONSTRAINT ip_number_aaaa_ip_u UNIQUE,

  mac_adr
    CHAR VARYING(30)
    DEFAULT NULL,

  CONSTRAINT dns_ip_number_entity_id
    FOREIGN KEY (entity_type, ipv6_number_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_zone
 *
 * The ``dns_zone`` is currently only used to group which hosts should be
 * included in the forward map.  It has the following columns::
 *
 *   zone           TODO - for multiple zones (affects name unique constr.)
 *   dns_owner_id   identifier (PK)
 *   entity_type    dns_owner (part of FK)
 *   mx_set_id      FK to mx_set
 *
 * The name is stored in entity_name.  By making it an entity,
 * netgroups becomes trivial.
 */
category:code;
CREATE TABLE dns_zone
(
  zone_id
    NUMERIC(12,0)
    CONSTRAINT dns_zone_pk PRIMARY KEY,

  name
    CHAR VARYING(30) NOT NULL
    CONSTRAINT zone_name_u UNIQUE,

  postfix
    CHAR VARYING(30)
    NULL
    UNIQUE
);


/*  dns_owner
 *
 * The ``dns_owner`` table represents the leftmost argument in a typical
 * zone file, typically a host-name.  It has the following columns::
 *
 *   zone           TODO - for multiple zones (affects name unique constr.)
 *   dns_owner_id   identifier (PK)
 *   entity_type    dns_owner (part of FK)
 *   mx_set_id      FK to mx_set
 *   expire_date    date when this entry is no longer valid
 *
 * The name is stored in entity_name.  By making it an entity,
 * netgroups becomes trivial.
 */
category:main;
CREATE TABLE dns_owner
(
  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT dns_owner_pk PRIMARY KEY,

  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_owner]
    NOT NULL
    CONSTRAINT a_record_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_owner]),

  zone_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT dns_owner_zone_fk
      REFERENCES dns_zone(zone_id),

  mx_set_id
    NUMERIC(12,0),

  expire_date
    DATE
    DEFAULT NULL,

  CONSTRAINT dns_owner_entity_id
    FOREIGN KEY (entity_type, dns_owner_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_a_record
 *
 * The ``dns_a_record`` table stores an a_record that maps between a
 * hostname and an IP.  It has the following columns::
 *
 *   entity_type        part of FK
 *   a_record_id        identifier (PK)
 *   dns_owner_id       FK to dns_owner
 *   ip_number_id       FK to ip_number
 *   ttl                optional TTL value 
 *   mac                mac address
 *
 * it is an entity so that we may register entity_note (comment/contact)
 * for it.
 *
 * TBD: we might want to only register such info for dns_owner entries.
 */
category:main;
CREATE TABLE dns_a_record
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_a_record]
    NOT NULL
    CONSTRAINT a_record_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_a_record]),

  a_record_id
    NUMERIC(12,0)
    CONSTRAINT a_record_pk PRIMARY KEY,

  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT a_record_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  ip_number_id
    NUMERIC(12,0)
    CONSTRAINT a_record_ip_fk
      REFERENCES dns_ip_number(ip_number_id),

  ttl
    NUMERIC(6,0),

  mac
    CHAR VARYING(128),

  CONSTRAINT a_record_ip_owner_u
    UNIQUE (ip_number_id, dns_owner_id)
);


/*  dns_aaaa_record
 *
 * The ``dns_aaaa_record`` table stores an a_record that maps between a
 * hostname and an IP.  It has the following columns::
 *
 *   entity_type        part of FK
 *   aaaa_record_id    identifier (PK)
 *   dns_owner_id       FK to dns_owner
 *   ipv6_number_id     FK to ip_number
 *   ttl                optional TTL value 
 *   mac                mac address
 *
 * it is an entity so that we may register entity_note (comment/contact)
 * for it.
 *
 * TBD: we might want to only register such info for dns_owner entries.
 */
category:main;
CREATE TABLE dns_aaaa_record
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_aaaa_record]
    NOT NULL
    CONSTRAINT a_record_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_aaaa_record]),

  aaaa_record_id
    NUMERIC(12,0)
    CONSTRAINT aaaa_record_pk PRIMARY KEY,

  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT aaaa_record_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  ipv6_number_id
    NUMERIC(12,0)
    CONSTRAINT aaaa_record_ip_fk
      REFERENCES dns_ipv6_number(ipv6_number_id),

  ttl
    NUMERIC(6,0),

  mac
    CHAR VARYING(128),

  CONSTRAINT aaaa_record_ip_owner_u
    UNIQUE (ipv6_number_id, dns_owner_id)
);


/*  dns_host_info
 *
 * The ``dns_host_info`` table store information about a host.  A host is
 * typically a hardware box.  It has the following columns::
 *
 *   entity_type    part of FK
 *   host_id        identifier (PK)
 *   dns_owner_id   FK to dns_owner
 *   ttl            optional TTL value
 *   hinfo          string representing hinfo
 *
 * it is an entity so that we may register entity_note (comment/contact)
 * for it.
 */
category:main;
CREATE TABLE dns_host_info
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_host]
    NOT NULL
    CONSTRAINT dns_host_info_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_host]),

  host_id
    NUMERIC(12,0)
    CONSTRAINT dns_host_info_pk PRIMARY KEY,

  dns_owner_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT host_info_owner_fk
      REFERENCES dns_owner(dns_owner_id)
      CONSTRAINT dns_host_info_dns_owner_id_u UNIQUE,

  ttl
    NUMERIC(6,0),

  hinfo
    CHAR VARYING(128)
    NULL,

  CONSTRAINT dns_host_info_entity_id
    FOREIGN KEY (entity_type, host_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_mx_set
 *
 * The ``dns_mx_set`` table defines a mx_set.  mx_set is used to
 * represent a collection of mx targets for a host.  The number of
 * sets is typically small.  It has the following columns::
 *
 *   mx_set_id   PK
 *   name        used in clients to identify the set
 */
category:main;
CREATE TABLE dns_mx_set
(
  mx_set_id
    NUMERIC(12,0)
    CONSTRAINT mx_set_pk PRIMARY KEY,

  name
    CHAR VARYING(64)
    NOT NULL
    CONSTRAINT mx_set_name_u UNIQUE
);


/* Delayed constraint due to circular dependency */
category:main;
ALTER TABLE dns_owner
  ADD CONSTRAINT dns_owner_mx_set_fk
  FOREIGN KEY (mx_set_id)
  REFERENCES dns_mx_set(mx_set_id);


/*  dns_mx_set_member
 *
 * The ``dns_mx_set_member`` table stores members of a mx_set.  It has
 * the following columns::
 *
 *   mx_set_id    FK to mx_set
 *   ttl          optional TTL value
 *   pri          priority
 *   target_id    FK to dns_owner
 *
 * The host that has an MX record is usually an A record, while the
 * target is usually a host.  We don't enforce this as there are
 * exceptions.
 */
category:main;
CREATE TABLE dns_mx_set_member
(
  mx_set_id
    NUMERIC(12,0)
    CONSTRAINT mx_set_fk
    REFERENCES dns_mx_set(mx_set_id),

  ttl
    NUMERIC(6,0),

  pri
    NUMERIC(3,0)
    NOT NULL,

  target_id
    NUMERIC(12,0)
    CONSTRAINT mx_set_target_fk
      REFERENCES dns_owner(dns_owner_id)
);


/*  dns_cname_record
 *
 * The ``dns_cname_record`` table stores cnames for an a_record.  It has
 * the following columns::
 *
 *   entity_type        part of FK
 *   cname_id           identifier (PK)
 *   cname_owner_id     FK to dns_owner
 *   ttl                optional TTL value
 *   target_owner_id    FK to dns_owner
 *
 * it is an entity so that one may attach entity_note to it.
 */
category:main;
CREATE TABLE dns_cname_record
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_cname]
    NOT NULL
    CONSTRAINT cname_record_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_cname]),

  cname_id
    NUMERIC(12,0)
    CONSTRAINT cname_record_pk PRIMARY KEY,

  cname_owner_id
    NUMERIC(12,0)
    CONSTRAINT cname_record_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  ttl
    NUMERIC(6,0),

  target_owner_id
    NUMERIC(12,0)
    CONSTRAINT cname_record_target_fk
      REFERENCES dns_owner(dns_owner_id),

  CONSTRAINT cname_record_entity_id
    FOREIGN KEY (entity_type, cname_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_field_type_code
 *
 * Defines the legal field types for the general_dns_record.  Typical
 * values are TXT, RP
 */
category:code;
CREATE TABLE dns_field_type_code
(
  code
    NUMERIC(6,0)
    CONSTRAINT field_type_code_pk PRIMARY KEY,

  code_str
    CHAR VARYING(16)
    NOT NULL
    CONSTRAINT field_type_codestr_u UNIQUE,

  description
    CHAR VARYING(512)
    NOT NULL
);


/*  dns_general_dns_record
 *
 * The ``dns_general_dns_record`` table stores A general record that has
 * some data and an optional TTL associated with a dns-owner.  TXT
 * records is one example.  It has the following columns::
 *
 *   dns_owner_id   FK to associated dns_owner
 *   field_type     FK to the corresponding dns_field_type_code
 *   ttl            optional TTL value
 *   data           data associated with this field_type
 */
category:main;
CREATE TABLE dns_general_dns_record
(
  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT a_record_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  field_type
    NUMERIC(6,0)
    NOT NULL
    CONSTRAINT field_type_code_fk
      REFERENCES dns_field_type_code(code),

  ttl
    NUMERIC(6,0),

  data
    CHAR VARYING(255)
    NOT NULL,

  CONSTRAINT general_dns_record_pk
    PRIMARY KEY (dns_owner_id, field_type)
);


/*  dns_override_reversemap
 *
 * By default, the reversemap is automatically deduced from dns_a_record
 * entry.  The ``dns_override_reversemap`` table can be used to override
 * this reversemap with another value.  It has the following columns::
 *
 *   ip_number_id    FK to ip_number
 *   dns_owner_id    FK to dns_owner
 *
 * Variants:
 *
 *   - Default: all A-records has a corresponding PTR record.  No entries
 *     in this table.
 *   - Only spesific A-records has a revmap:
 *     a_record:(A -> IP) reverse:(IP -> A)
 *   - No revmap:
 *     a_record(A -> IP) reverse(:IP -> NULL)
 *   - revmap for something with no A-record:
 *     reverse:(IP -> A)
 */
category:main;
CREATE TABLE dns_override_reversemap
(
  ip_number_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT override_reversemap_ip_fk
      REFERENCES dns_ip_number(ip_number_id),

  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT override_reversemap_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  CONSTRAINT dns_override_reversemap_u
    UNIQUE (ip_number_id, dns_owner_id)
);

category:main;
CREATE INDEX dns_over_revmap_ip_idx
  ON dns_override_reversemap(ip_number_id);


/*  dns_override_reversemap_ipv6
 *
 * By default, the reversemap is automatically deduced from dns_aaaa_record
 * entry.  The ``dns_override_reversemap_ipv6`` table can be used to override
 * this reversemap with another value.  It has the following columns::
 *
 *   ipv6_number_id    FK to ipv6_number
 *   dns_owner_id    FK to dns_owner
 *
 * Variants:
 *
 *   - Default: all AAAA-records has a corresponding PTR record.  No entries
 *     in this table.
 *   - Only spesific AAAA-records has a revmap:
 *     aaaa_record:(AAAA -> IP) reverse:(IP -> AAAA)
 *   - No revmap:
 *     aaaa_record(AAAA -> IP) reverse(:IP -> NULL)
 *   - revmap for something with no AAAA-record:
 *     reverse:(IP -> AAAA)
 */
category:main;
CREATE TABLE dns_override_reversemap_ipv6
(
  ipv6_number_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT override_reversemap_ipv6_fk
      REFERENCES dns_ipv6_number(ipv6_number_id),

  dns_owner_id
    NUMERIC(12,0)
    CONSTRAINT override_reversemap_ipv6_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  CONSTRAINT dns_override_reversemap_ipv6_u
    UNIQUE (ipv6_number_id, dns_owner_id)
);

category:main;
CREATE INDEX dns_over_revmap_ipv6_idx
  ON dns_override_reversemap_ipv6(ipv6_number_id);


/*  dns_srv_record
 *
 * The ``dns_srv_record`` table stores a SRV (service) record (RFC 2782).
 *
 * It seems that the PK should span all-rows except ttl
 *
 * Example of this record type::
 *
 *   <service> <ttl> SRV <priority> <weight> <port> <hostname>
 *   _http._tcp.example.com. SRV 10 5 80. www.example.com
 *
 * The table has the following columns::
 *
 *   service_owner_id   FK to dns_owner
 *   pri                priority
 *   weight             weight
 *   port               port
 *   ttl                optional TTL value
 *   target_owner_id    FK to the dns_owner being a target for this SRV record
 */
category:main;
CREATE TABLE dns_srv_record
(
  service_owner_id
    NUMERIC(12,0)
    CONSTRAINT srv_record_service_owner_fk
      REFERENCES dns_owner(dns_owner_id),

  pri
    NUMERIC(3,0)
    NOT NULL,

  weight
    NUMERIC(3,0)
    NOT NULL,

  port
    NUMERIC(5,0)
    NOT NULL,

  ttl
    NUMERIC(6,0),

  target_owner_id
    NUMERIC(12,0)
    CONSTRAINT srv_record_target_owner_fk
      REFERENCES dns_owner(dns_owner_id)
);

/*  dns_reserved_host
 *
 * Contains hostnames that are illegal to use.  Will probably not be used.
 */
/*
category:main;
CREATE TABLE dns_reserved_host
(
  id
    CHAR VARYING(128)
);
*/


/*  dns_subnet
 */
category:main;
CREATE TABLE dns_subnet
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_subnet]
    NOT NULL
    CONSTRAINT dns_subnet_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_subnet]),

  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT dns_subnet_pk PRIMARY KEY,

  subnet_ip
    CHAR VARYING(18)
    NOT NULL
    CONSTRAINT dns_subnet_ip_uniq UNIQUE,

  ip_min
    NUMERIC(12,0)
    NOT NULL,

  ip_max
    NUMERIC(12,0)
    NOT NULL,

  description
    CHAR VARYING(512)
    NOT NULL
    DEFAULT '',

  dns_delegated
    BOOLEAN
    NOT NULL
    DEFAULT FALSE,

  name_prefix
    CHAR VARYING(128)
    NOT NULL
    DEFAULT '',

  vlan_number
    NUMERIC(12,0)
    DEFAULT NULL,

  no_of_reserved_adr
    NUMERIC(3,0)
    NOT NULL
    DEFAULT 3,

  CONSTRAINT dns_subnet_entity_info
    FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id)
);


/*  dns_ipv6_subnet
 *
 * Separate table to hold subnets for IPv6. This is modeled after dns_subnet.
 *
 */
category:main;
CREATE TABLE dns_ipv6_subnet
(
  entity_type
    NUMERIC(6,0)
    DEFAULT [:get_constant name=entity_dns_ipv6_subnet]
    NOT NULL
    CONSTRAINT dns_ipv6_subnet_entity_type_chk
      CHECK (entity_type = [:get_constant name=entity_dns_ipv6_subnet]),

  entity_id
    NUMERIC(12,0)
    NOT NULL
    CONSTRAINT dns_ipv6_subnet_pk PRIMARY KEY,

  subnet_ip
    CHAR VARYING(39)
    NOT NULL
    CONSTRAINT dns_ipv6_subnet_ip_uniq UNIQUE,

  ip_min
    NUMERIC(39,0)
    NOT NULL,

  ip_max
    NUMERIC(39,0)
    NOT NULL,

  description
    CHAR VARYING(512)
    NOT NULL
    DEFAULT '',

  dns_delegated
    BOOLEAN
    NOT NULL
    DEFAULT FALSE,

  name_prefix
    CHAR VARYING(128)
    NOT NULL
    DEFAULT '',

  vlan_number
    NUMERIC(12,0)
    DEFAULT NULL,

  no_of_reserved_adr
    NUMERIC(3,0)
    NOT NULL
    DEFAULT 3,

  CONSTRAINT dns_ipv6_subnet_entity_info
    FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id)
);

