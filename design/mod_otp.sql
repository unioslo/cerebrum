/* encoding: utf-8
 *
 * Copyright 2021 University of Oslo, Norway
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
 * Tables used by Cerebrum.modules.otp
 *
 * This module adds tables for storing *personal* otp secrets for multiple
 * target systems.
 *
 */
category:metainfo;
name=otp;

category:metainfo;
version=1.0;


/* TABLE person_otp_secret
 *
 * person_id
 *   reference to person
 *
 * otp_type
 *   identifies a multifactor auth/otp type
 *
 * otp_payload
 *   encrypted otp secret
 *
 *   format and encryption type is identified by otp_type, and its companion
 *   module in Cerebrum.modules.otp
 *
 * updated_at
 *   last change timestamp -- when the item was added/modified
 */
category:main;
CREATE TABLE IF NOT EXISTS person_otp_secret
(
  person_id
    NUMERIC(12,0)
    NOT NULL
    REFERENCES person_info(person_id),

  otp_type
    TEXT
    NOT NULL
    CONSTRAINT person_otp_secret_type_chk
      CHECK (otp_type != ''),

  otp_payload
    TEXT
    NOT NULL
    DEFAULT '',

  updated_at
    TIMESTAMP WITH TIME ZONE
    NOT NULL
    DEFAULT [:now],

  CONSTRAINT person_otp_secret_pk
    PRIMARY KEY (person_id, otp_type)
);

/* trigger function to modify updated_at */
category:main;
CREATE OR REPLACE FUNCTION person_otp_set_updated_at()
RETURNS TRIGGER AS '
  BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
  END;
' LANGUAGE plpgsql;

/* Add trigger to automatically set person_otp_secret.updated_at */
category:main;
CREATE TRIGGER person_otp_update_trigger
    BEFORE UPDATE ON person_otp_secret
    FOR EACH ROW
    EXECUTE PROCEDURE person_otp_set_updated_at();


category:drop;
DROP TRIGGER person_otp_update_trigger ON person_otp_secret;

category:drop;
DROP FUNCTION person_otp_set_updated_at();

category:drop;
DROP TABLE IF EXISTS person_otp_secret;
