/*
 * Copyright 2012 University of Oslo, Norway
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
 */

/* SQL script for migrating mod_dns 1.2 to 1.3 */


category:drop;
DROP TABLE dns_aaaa_record;
category:drop;
DROP TABLE dns_ipv6_number;

/*	dns_ipv6_number

The ``dns_ipv6_number`` table stores an IPv6_number.  We store IPv6-numbers
in a separate table to make unique-constaint and consistent updates to
dns_aaaa_record and dns_override_reversemap_ipv6 easier.  It has the following
columns::

  ipv6_number_id  identifier (PK)
  aaaa_ip       ip (v6) address
  mac_adr       MAC address
*/
category:pre;
CREATE TABLE dns_ipv6_number (
  entity_type	NUMERIC(6,0)
		DEFAULT [:get_constant name=entity_dns_ipv6_number]
		NOT NULL
		CONSTRAINT dns_ipv6_number_entity_type_chk
		  CHECK (entity_type = [:get_constant name=entity_dns_ipv6_number]),
  ipv6_number_id  NUMERIC(12,0)
                  CONSTRAINT ipv6_number_pk PRIMARY KEY,
  aaaa_ip       CHAR VARYING(39)
                CONSTRAINT ip_number_aaaa_ip_u UNIQUE,
  mac_adr       CHAR VARYING(30) DEFAULT NULL,
  CONSTRAINT dns_ip_number_entity_id
    FOREIGN KEY (entity_type, ipv6_number_id)
    REFERENCES entity_info(entity_type, entity_id)
);

/*	dns_aaaa_record

The ``dns_aaaa_record`` table stores an a_record that maps between a
hostname and an IP.  It has the following columns::

  entity_type        part of FK
  aaaa_record_id    identifier (PK)
  dns_owner_id       FK to dns_owner
  ipv6_number_id     FK to ip_number
  ttl                optional TTL value 
  mac                mac address

it is an entity so that we may register entity_note (comment/contact)
for it.

TBD: we might want to only register such info for dns_owner entries.
*/

category:pre;
CREATE TABLE dns_aaaa_record (
  entity_type   NUMERIC(6,0)
                DEFAULT [:get_constant name=entity_dns_aaaa_record]
                NOT NULL
                CONSTRAINT a_record_entity_type_chk
                  CHECK (entity_type = [:get_constant name=entity_dns_aaaa_record]),
  aaaa_record_id   NUMERIC(12,0)
                  CONSTRAINT aaaa_record_pk PRIMARY KEY,
  dns_owner_id  NUMERIC(12,0)
                  CONSTRAINT aaaa_record_owner_fk 
                  REFERENCES dns_owner(dns_owner_id),
  ipv6_number_id  NUMERIC(12,0)
                  CONSTRAINT aaaa_record_ip_fk 
                  REFERENCES dns_ipv6_number(ipv6_number_id),
  ttl           NUMERIC(6,0), 
  mac           CHAR VARYING(128),
  CONSTRAINT aaaa_record_ip_owner_u
    UNIQUE (ipv6_number_id, dns_owner_id)
);

/*	dns_override_reversemap_ipv6

By default, the reversemap is automatically deduced from dns_aaaa_record
entry.  The ``dns_override_reversemap_ipv6`` table can be used to override
this reversemap with another value.  It has the following columns::

  ipv6_number_id    FK to ipv6_number
  dns_owner_id    FK to dns_owner

Variants:

  - Default: all AAAA-records has a corresponding PTR record.  No entries
    in this table.
  - Only spesific AAAA-records has a revmap:
    aaaa_record:(AAAA -> IP) reverse:(IP -> AAAA)
  - No revmap: 
    aaaa_record(AAAA -> IP) reverse(:IP -> NULL)
  - revmap for something with no AAAA-record: 
    reverse:(IP -> AAAA)
*/

category:pre;
CREATE TABLE dns_override_reversemap_ipv6 (
  ipv6_number_id  NUMERIC(12,0) NOT NULL
                  CONSTRAINT override_reversemap_ipv6_fk 
                  REFERENCES dns_ipv6_number(ipv6_number_id),
  dns_owner_id  NUMERIC(12,0)
                  CONSTRAINT override_reversemap_ipv6_owner_fk 
                  REFERENCES dns_owner(dns_owner_id),
  CONSTRAINT dns_override_reversemap_ipv6_u
    UNIQUE (ipv6_number_id, dns_owner_id)
);
category:main;
CREATE INDEX dns_over_revmap_ipv6_idx ON dns_override_reversemap_ipv6(ipv6_number_id);

