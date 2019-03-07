# -*- coding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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


"""This module implements authentication framework for voip.

The voip module contains a number of password-like attributes. This module
offers an interface to password-like storage in the database for any entity in
Cerebrum.

FIXME: This ought to be made more generic, so that we can use this module for
account password storage.

FIXME: Merge with PasswordChecker.py
"""

import cereconf


from Cerebrum import Errors
from Cerebrum.Entity import Entity
from Cerebrum.Utils import argument_to_sql
from Cerebrum.Errors import CerebrumError


class EntityAuthentication(Entity):
    """Class for supporting authentication data in voip.

    We have a number of entities in voip that need to store various
    authentication information (either plaintext or encrypted). This class
    provides support for storing/retrieving such credentials from Cerebrum.
    """

    def delete(self):
        """Nuke all the auth data pertinent to this entity."""
        
        self.execute("""
        DELETE FROM [:table schema=cererbum name=entity_authentication_info]
        WHERE entity_id = :entity_id
        """, {"entity_id": self.entity_id})
        self.__super.delete()
    # end delete

    def get_auth_methods(self):
        """Returns a list of the auth methods registered for this entity."""

        return self.query("""
        SELECT auth_method
        FROM [:table schema=cererbum name=entity_authentication_info]
        WHERE entity_id = :entity_id""", {"entity_id": self.entity_id})
    # end get_auth_methods

    def get_auth_data(self, auth_method):
        """Return specific auth data for the method specified."""

        try:
            return self.query_1("""
            SELECT auth_data
            FROM [:table schema=cererbum name=entity_authentication_info]
            WHERE entity_id = :entity_id AND
            auth_method = :auth_method
            """, {"entity_id": self.entity_id,
                  "auth_method": int(auth_method)})
        except Errors.NotFoundError:
            return None
    # end get_auth_data

    def set_auth_data(self, auth_method, auth_data):
        """Register new auth data of the specified type.

        If the entity had an entry for that auth type, it's silently
        overwritten with auth_data.

        If auth_data is None, the corresponding entry (i.e. the proper
        auth_method's row for self) will be removed. IOW this method can be
        used to delete authentication data.
        """

        binds = {"entity_id": self.entity_id,
                 "auth_method": int(auth_method),
                 "auth_data": auth_data}

        if not self.validate_auth_data(auth_method, auth_data):
            raise CerebrumError("Invalid auth_data '%s' for auth_method %s" %
                                (auth_data,
                                 str(self.const.EntityAuthentication(auth_method))))

        if auth_data is None:
            self.execute("""
            DELETE FROM [:table schema=cererbum name=entity_authentication_info]
            WHERE entity_id = :entity_id AND
                  auth_method = :auth_method
            """, binds)
            return

        auth_in_db = self.get_auth_data(auth_method)
        if not auth_in_db:
            self.execute("""
            INSERT INTO [:table schema=cererbum name=entity_authentication_info]
            VALUES (:entity_id, :auth_method, :auth_data)
            """, binds)
        elif auth_in_db != auth_data:
            self.execute("""
            UPDATE [:table schema=cererbum name=entity_authentication_info]
            SET auth_data = :auth_data
            WHERE entity_id = :entity_id AND
                  auth_method = :auth_method
            """, binds)
    # end set_auth_data

    def validate_auth_data(self, auth_method, auth_data):
        """Check that auth_data follows the rules for auth_method.

        If it does not, raise CerebrumError.
        """

        # By default we delegate this task to the subclasses.
        return True
    # end validate_auth_data

    def list_auth_data(self, auth_methods=None):
        """Return all authentication data registered for the given methods.

        @type auth_methods: an int, an EntityAuthenticationCode or a sequence
        thereof.
        @param auth_methods:
          Specify which authentication methods the data should be returned
          for. 
        """

        binds = dict()
        where = ""
        if auth_methods is not None:
            where = argument_to_sql(auth_methods, "auth_method", binds, int)

        return self.query("""
        SELECT entity_id, auth_method, auth_data
        FROM [:table schema=cerebrum name=entity_authentication_info]
        WHERE """ + where, binds)
    # end list_auth_data
# end EntityAuthentication
