/*
 * Copyright 2003 University of Oslo, Norway
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

category:main;
CREATE TABLE ad_entity
(
  entity_type   NUMERIC(6,0)
                NOT NULL,
  entity_id     NUMERIC(12,0)
                CONSTRAINT ad_entity_pk PRIMARY KEY,
  ou_id         NUMERIC(12,0)
                NOT NULL
		CONSTRAINT ad_entity_ou_id REFERENCES ou_info(ou_id),
  CONSTRAINT ad_entity_entity_id FOREIGN KEY (entity_type, entity_id)
    REFERENCES entity_info(entity_type, entity_id),
  CONSTRAINT ad_entity_entity_type_chk
    CHECK (entity_type IN ([:get_constant name=entity_account],
			   [:get_constant name=entity_group]))
);

/*

  'login_script'   NULL => Don't run any login script for this user;
		   deal with things through policies etc.

  'home_dir'	   NULL => Don't connect any home directory when
		   this user logs in.

*/
category:main;
CREATE TABLE ad_account
(
  account_id    NUMERIC(12,0)
                CONSTRAINT ad_account_pk PRIMARY KEY
		CONSTRAINT ad_account_account_id
		  REFERENCES account_info(account_id)
		CONSTRAINT ad_account_account_id2
		  REFERENCES ad_entity(entity_id),
  login_script  CHAR VARYING(128),
  home_dir      CHAR VARYING(128)
);

/*

Ekstra-informasjon som ikke finnes i Cerebrum:

 * OU:
   - Ønsker mer finmasket oppdeling av OU-strukturen.
        OU=Hovedfag,OU=Ifi,OU=MNF,dc=uio,dc=no
        OU=Laveregrad,OU=Ifi,OU=MNF,dc=uio,dc=no
        OU=Labkurs,OU=Laveregrad,OU=KI,OU=MNF,dc=uio,dc=no
*/

category:drop;
DROP TABLE ad_account;
category:drop;
DROP TABLE ad_entity;

/* arch-tag: aa131b66-5b6a-482b-bd71-34f121232a70
   (do not change this comment) */
