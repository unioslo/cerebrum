/*
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
 * Tables used by Cerebrum.modules.apikeys
 *
 * This module stores API client identifiers from an API gateway, along with a
 * hash of the api keys. The idea is to whitelist client keys without storing
 * the keys in plaintext.
 */
category:metainfo;
name=apikeys;

category:metainfo;
version=1.0;

/**
 * Table to map api clients to user accounts.
 *
 * identifier
 *   A unique client identifier to whitelist.
 * account_id
 *   Account to map API key to.
 * updated_at
 *   Timestamp of the last change to the record. This value should never be
 *   set explicitly, but maintained by default value or trigger.
 * description
 *   An optional description of this client/key.
**/
category:main;
CREATE TABLE apikey_client_map (
  identifier    CHAR VARYING(256)
                NOT NULL,
  account_id    NUMERIC(12,0)
                NOT NULL
                REFERENCES account_info(account_id),
  updated_at    TIMESTAMP
                WITH TIME ZONE
                NOT NULL
                DEFAULT [:now],
  description   TEXT,
  CONSTRAINT apikey_client_map_pk PRIMARY KEY (identifier)
);

/* function to create a trigger that sets updated_at */
category:main;
CREATE OR REPLACE FUNCTION apikey_set_update()
RETURNS TRIGGER AS '
  BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
  END;
' LANGUAGE plpgsql;

/* Add trigger to automatically set apikey_client_map.updated_at */
category:main;
CREATE TRIGGER apikey_set_update_trigger
    BEFORE UPDATE ON apikey_client_map
    FOR EACH ROW
    EXECUTE PROCEDURE apikey_set_update();

category:drop;
DROP TRIGGER apikey_set_update_trigger ON apikey_client_map;

category:drop;
DROP FUNCTION apikey_set_update();

category:drop;
DROP TABLE apikey_client_map;
