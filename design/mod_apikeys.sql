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
 * This module stores API keys from an API gateway in a whitelist table, and
 * maps API-keys to user accounts.
 */
category:metainfo;
name=apikeys;

category:metainfo;
version=1.0;

/**
 * account_id
 *   Account to map API key to
 * value
 *   The API key value
**/
category:main;
CREATE TABLE account_apikey (
  account_id    NUMERIC(6,0)
                REFERENCES account_info(account_id),
  value         CHAR VARYING(128)
                NOT NULL
                UNIQUE,
  updated_at    TIMESTAMP
                WITH TIME ZONE
                NOT NULL
                DEFAULT [:now]
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

/* Add trigger to automatically set account_apikey.updated_at */
category:main;
CREATE TRIGGER apikey_set_update_trigger
    BEFORE UPDATE ON account_apikey
    FOR EACH ROW
    EXECUTE PROCEDURE apikey_set_update();

category:drop;
DROP TRIGGER apikey_set_update_trigger ON account_apikey;

category:drop;
DROP FUNCTION apikey_set_update();

category:drop;
DROP TABLE account_apikey;
