/* encoding: utf-8
 *
 * Copyright 2019 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.no.uit.ad_email
 *
 * This module is based on a table from cerebrum @ uit:
 *
 *                   Table "public.ad_email"
 *
 *     Column     |            Type       | Modifiers
 *  --------------+-----------------------+-----------
 *   account_name | character varying(20) | not null
 *   local_part   | character varying(64) | not null
 *   domain_part  | character varying(64) | not null
 *   create_date  | date                  |
 *   update_date  | date                  |
 *  Indexes:
 *      "ad_email_pkey" PRIMARY KEY, btree (account_name, local_part, domain_part)
 *
 * The primary key could just be account_name, but for some unknown reason it is not.
 * Might be something that should be fixed when migrating
 */
category:metainfo;
name=ad_email;

category:metainfo;
version=1.0;


/*  ad_email
 *
 * Table of ad_emails connected to accounts
 *
 * account_name
 *   The account connected to the mail address
 * local_part
 *   The local part of the mail address
 * domain_part
 *   The domain part of the mail address
 * create_date
 *   The date this entry was made
 * update_date
 *   The date this entry was last updated
 */
category:main;
CREATE TABLE ad_email
(
  account_name
    CHAR VARYING (20)
    NOT NULL,

  local_part
    CHAR VARYING (64)
    NOT NULL,

  domain_part
    CHAR VARYING (64)
    NOT NULL,

  create_date
    DATE,

  update_date
    DATE,

  CONSTRAINT ad_email_pkey PRIMARY KEY (account_name, local_pary, domain_part)
);


category:drop;
DROP TABLE ad_email;
