# Copyright 2002 University of Oslo, Norway
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

"""The ADUser module is used as a mixin-class for Account, and
contains additional parameters that are required for building Accounts in
Active Directory.  This includes the OU(as defined in AD) a group or user is
connected to. The ADUser also got to new values defined, login script and
home directory.

The user name is inherited from the superclass, which here is Entity."""

import string
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.Entity import Entity, EntityName, EntityQuarantine
from Cerebrum.Utils import Factory

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

class ADObject(Entity, EntityName, EntityQuarantine):
# Bare arve egenskaper fra Entity?

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('ou_id',)

    def clear(self):
        self.__super.clear()
        for attr in ADObject.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in ADObject.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def __eq__(self, other):
        assert isinstance(other, ADObject)
        if self.ou_id   == other.ou_id:
            return self.__super.__eq__(other)
        return False   


    def populate(self, type, ou):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False        
        Entity.populate(self, type)
        self.ou_id = ou
        

    def write_db(self):
#                 
#        self.__super.write_db()
        if not self.__updated:
            return
        if not self.__in_db:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ad_entity]
              (entity_type, entity_id, ou_id)
            VALUES (:e_type, :e_id, :e_ou)""",
                         {'e_type': int(self.entity_type),
                          'e_id': int(self.entity_id),
                          'e_ou': int(self.ou_id)})

        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=ad_entity]
            SET ou_id=:e_ou, entity_type=:e_type
            WHERE entity_id=:e_id""", {'e_type': int(self.entity_type),
                                       'e_id': int(self.entity_id),
                                       'e_ou': int(self.ou_id)})
        del self.__in_db
        self.__in_db = True
        self.__updated = False

    def find(self, entity_id):
        """Associate the object with the ADUser whose identifier is account_id.

        If account_id isn't an existing ID identifier,
        NotFoundError is raised."""
        self.__super.find(entity_id)
        (self.ou_id) = self.query_1("""
        SELECT ou_id
        FROM [:table schema=cerebrum name=ad_entity]
        WHERE entity_id=:entity_id""", {'entity_id': entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def list_ad_objects(self,e_type):
        "get all users in the ad table"
        return self.query("""
        SELECT entity_id,ou_id
        FROM [:table schema=cerebrum name=ad_entity]
        WHERE entity_type=:e_type""",
                          {'e_type': int(e_type)})
