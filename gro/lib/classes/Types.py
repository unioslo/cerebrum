# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import Cerebrum.Entity
import Database

from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute
from Searchable import Searchable

__all__ = ['AddressType', 'ContactInfoType', 'GenderType', 'EntityType',
           'SourceSystem', 'NameType', 'AuthenticationType', 'Spread',
           'GroupMemberOperationType', 'GroupVisibilityType', 'QuarantineType',
           'OUPerspectiveType', 'AuthOperationType']

class CodeType(Builder, Searchable):
    primary = [Attribute('name', 'string')]
    slots = primary + [Attribute('id', 'long'),
                       Attribute('description', 'string')]

    def get_by_id(cls, id):
        rows = Database.get_database().query('''SELECT code_str, description
                           FROM %s WHERE code = %s''' % (cls._tableName, id))
        if not rows:
            raise Errors.NoSuchNodeError('%s(%s) not found' % (cls.__name__, id))
        row = rows[0]

        name = row['code_str']
        description = row['description']

        return cls(id, name=name, description=description)

    get_by_id = classmethod(get_by_id)

    def _load(self):
        rows = Database.get_database().query('''SELECT code, description
                           FROM %s WHERE code_str = %s''' % (self._tableName, `self._name`)) # ugh. stygg escaping
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (self.__class__.__name__, self._name))
        row = rows[0]

        self._id = int(row['code'])
        self._description = row['description']

    load_id = load_description = _load

    def create_search_method(cls):
        def search(self, id=None, name=None, description=None):
            def prepare_string(value):
                value = value.replace("*", "%")
                value = value.replace("?", "_")
                value = value.lower()
                return value

            where = []
            if id is not None:
                where.append('code = %i' % entity.get_id())
            if name is not None:
                where.append('LOWER(code_str) LIKE :name')
                name = prepare_string(name)
            if description is not None:
                where.append('LOWER(description) LIKE :description')
                description = prepare_string(description)

            if where:
                where = 'WHERE %s' % ' AND '.join(where)
            else:
                where = ''

            objects = []
            db = self.get_database()
            for row in db.query("""SELECT code, code_str, description
                                   FROM [:table schema=cerebrum name=%s]
                                   %s""" % (cls._tableName, where),
                                            {'name':name, 'description':description}):
                id = int(row['code'])
                name = row['code_str']
                description = row['description']
                objects.append(cls(id=id, name=name, description=description))
            return objects
        return search
    create_search_method = classmethod(create_search_method)

class AddressType(CodeType):
    _tableName = 'address_code'

class ContactInfoType(CodeType):
    _tableName = 'contact_info_code'

class GenderType(CodeType):
    _tableName = 'gender_code'

class AffiliationType(CodeType):
    _tableName = 'person_affiliation_code'

class EntityType(CodeType):
    _tableName = 'entity_type_code'

    def get_class(self):
        import Account, Disk, Group, Host, OU, Person
        if self.get_name() == 'account':
            return Account.Account
        elif self.get_name() == 'disk':
            return Disk.Disk
        elif self.get_name() == 'group':
            return Group.Group
        elif self.get_name() == 'host':
            return Host.Host
        elif self.get_name() == 'ou':
            return OU.OU
        elif self.get_name() == 'person':
            return Person.Person

class SourceSystem(CodeType):
    _tableName = 'authoritative_system_code'

class NameType(CodeType):
    _tableName = 'person_name_code'

class AuthenticationType(CodeType):
    _tableName = 'authentication_code'

class GroupMemberOperationType(CodeType):
    _tableName = 'group_membership_op_code'

class GroupVisibilityType(CodeType):
    _tableName = 'group_visibility_code'

class OUPerspectiveType(CodeType):
    _tableName = 'ou_perspective_code'

class QuarantineType(CodeType):
    _tableName = 'quarantine_code'

class Spread(CodeType):
    _tableName = 'spread_code'

class AuthOperationType(CodeType):
    _tableName = 'auth_op_code'

