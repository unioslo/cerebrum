#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
""" This module contains a client that can communicate with the CIM WS. """

import requests
import json
import jsonschema
import random

from requests.exceptions import (HTTPError,
                                 ConnectionError,
                                 Timeout)

from Cerebrum.Utils import read_password


class CIMClient(object):
    """Client for communicating with the CIM JSON web service."""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.schema = self._get_schema()
        self.auth = self._get_auth()

    def _get_auth(self):
        """Reads the password from file and returns the credentials.

        :return tuple:
            Username and password.
        """
        self.logger.debug("CIMClient: Caching credentials")
        password = read_password(
            user=self.config.auth_user,
            system=self.config.auth_system,
            host=self.config.auth_host)
        return (self.config.auth_user, password)

    def _get_schema(self):
        """Fetches the JSON schema from the web service.

        :return str:
            The JSON schema.
        """
        schema_url = self.config.api_url + 'UserImport.json'
        self.logger.debug(
            "CIMClient: Fetching schema from {}".format(schema_url))
        schema = requests.get(schema_url)
        return schema.json()

    def _make_payload(self, data):
        """Makes the query parameters expected by the web service.

        :return dict:
            The payload.
        """
        # Why are we using a random float as the time, you ask?
        # If we use the same value for two consecutive requests to the web
        # service, we'll be denied.
        payload = {
            'time': random.random(),
            'generic': json.dumps(data)
        }
        if self.config.dry_run:
            payload['dry_run'] = 1
        return payload

    def _handle_response(self, response):
        """Takes a `Response`, determines whether the request was succesful
        and logs any errors.

        :return bool:
            Successful?
        """
        try:
            response.raise_for_status()
        except HTTPError, e:
            self.logger.warning(
                "CIMClient: HTTP error {} from CIM WS: {}".format(
                    response.status_code,
                    response.text))
            return False
        except (ConnectionError, Timeout), e:
            self.logger.error(
                "CIMClient: Error communicating with CIM WS: {!r}".format(
                    e.message))
            return False
        finally:
            self.logger.debug("CIMClient: Got {} {} after {} seconds".format(
                response.status_code,
                response.reason,
                response.elapsed.total_seconds()))
        return True

    def validate(self, data):
        """Validates data against the JSON schema.

        :param list data:
            Data to be validated.
        :raises ValidationError:
            If the data is invalid.
        :raises SchemaError:
            If the schema is invalid.
        """
        jsonschema.validate(data, self.schema)

    def update_user(self, userdata):
        """Inserts or updates a user.

        :param dict userdata:
            User data matching the object in the JSON schema.
        :return bool:
            Successful?
        :raises ValidationError:
            If the data is invalid.
        """
        endpoint = 'update.json.php'
        data = [userdata]
        self.validate(data)
        payload = self._make_payload(data)
        self.logger.debug("CIMClient: Calling {} for {!r}".format(
            endpoint, userdata.get('username')))
        response = requests.post(self.config.api_url + endpoint,
                                 data=payload,
                                 auth=self.auth)
        return self._handle_response(response)

    def delete_user(self, username):
        """Deletes a user.

        :param str username:
            Name of the user to be deleted.
        :return bool:
            Successful?
        """
        endpoint = 'delete.json.php'
        data = [username]
        payload = self._make_payload(data)
        self.logger.debug("CIMClient: Calling {} for {!r}".format(
            endpoint, username))
        response = requests.post(self.config.api_url + endpoint,
                                 data=payload,
                                 auth=self.auth)
        return self._handle_response(response)
