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

import Registry
registry = Registry.get_registry()

Builder = registry.Builder
Attribute = registry.Attribute
Searchable = registry.Searchable

__all__ = ['AddressType', 'ContactInfoType', 'GenderType', 'EntityType',
           'SourceSystem', 'NameType', 'AuthenticationType', 'Spread',
           'GroupMemberOperationType', 'GroupVisibilityType', 'QuarantineType',
           'OUPerspectiveType', 'AuthOperationType']

class CodeType(Builder, Searchable):
    primary = [Attribute('name', 'string')]
    slots = primary + [Attribute('id', 'long'),
                       Attribute('description', 'string')]

    def create_primary_key(cls, name=None, id=None, description=None):
        # creates primary key for CodeType.
        # This will actually make it possible for a constant
        # to have 2 instances in the cache, which is a bad thing.
        # We do this because we dont want to ask the database
        # for a name when we get a object by id, since we have
        # name as primary key.
        if name is not None:
            assert type(name) == str
            return (name, )
        elif id is not None:
            assert type(id) == int
            return (id, )
        assert 0

    create_primary_key = classmethod(create_primary_key)

    def __eq__(self, other):
        """ Check of self and other has the same id """
        if self is other:
            return True
        else:
            return self.get_id() == other.get_id()

    def __hash__(self):
        """ return the hash of the name """
        return hash(self.get_name())

    def _load(self):
        db = self.get_database()

        id = name = None

        if hasattr(self, '_id'):
            id = self._id
            where = 'code = :id'
        else:
            name = self._name
            where = 'code_str = :name'

        row = db.query_1('''SELECT code, code_str, description
                            FROM %s WHERE %s''' % (self._tableName, where), {'id':id, 'name':name})
        self._id = int(row['code'])
        self._name = row['code_str']
        self._description = row['description']

    load_id = load_name = load_description = _load

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
        name = self.get_name()
        if name == 'account':
            return registry.Account
        elif name == 'disk':
            return registry.Disk
        elif name == 'group':
            return registry.Group
        elif name == 'host':
            return registry.Host
        elif name == 'ou':
            return registry.OU
        elif name == 'person':
            return registry.Person

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

# arch-tag: 8c22fbba-ab80-405e-8d56-1e62b7da1cae
