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

category:drop;
DROP TABLE dns_ipv6_subnet;

category:pre;
CREATE TABLE dns_ipv6_subnet
(
   entity_type        NUMERIC(6,0)
	 	      DEFAULT [:get_constant name=entity_dns_ipv6_subnet]
  		      NOT NULL
		      CONSTRAINT dns_ipv6_subnet_entity_type_chk
 		         CHECK (entity_type = [:get_constant
                    name=entity_dns_ipv6_subnet]),
   entity_id          NUMERIC(12,0)
 		      NOT NULL
		      CONSTRAINT dns_ipv6_subnet_pk PRIMARY KEY,
   subnet_ip          CHAR VARYING(39)
 		      NOT NULL
		      CONSTRAINT dns_ipv6_subnet_ip_uniq UNIQUE,
   ip_min	      NUMERIC(39,0)
   		      NOT NULL,
   ip_max	      NUMERIC(39,0)
   		      NOT NULL,
   description        CHAR VARYING(512)
 		      NOT NULL
   		      DEFAULT '',
   dns_delegated      BOOLEAN
   		      NOT NULL
		      DEFAULT FALSE,
   name_prefix        CHAR VARYING(128)
   		      NOT NULL
   		      DEFAULT '',
   vlan_number	      NUMERIC(12,0)
   		      DEFAULT NULL,
   no_of_reserved_adr NUMERIC(3,0)
		      NOT NULL
		      DEFAULT 3,

   CONSTRAINT dns_ipv6_subnet_entity_info FOREIGN KEY (entity_type, entity_id) 
   	      			     REFERENCES entity_info(entity_type, entity_id)
);

