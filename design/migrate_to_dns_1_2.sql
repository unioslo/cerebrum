/*
 * Copyright 2009 University of Oslo, Norway
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

/* SQL script for migrating mod_dns 1.1 to 1.2 */


category:pre;
ALTER TABLE dns_ip_number ADD mac_adr CHAR VARYING(30) DEFAULT NULL;


/* 
 * The following two statements are simply fix for an incorrectly
 * named constraint
*/
category:pre;
ALTER TABLE dns_ip_number 
   DROP CONSTRAINT group_info_entity_type_chk;

category:pre;
ALTER TABLE dns_ip_number 
   ADD CONSTRAINT dns_ip_number_entity_type_chk 
       CHECK (entity_type = [:get_constant name=entity_dns_ip_number]);
