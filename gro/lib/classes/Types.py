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

from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute
from db import db

__all__ = ['AddressType', 'ContactInfoType', 'GenderType', 'EntityType',
           'SourceSystem', 'NameType', 'AuthenticationType', 'Spread',
           'GroupMemberOperationType', 'GroupVisibilityType', 'QuarantineType']

class CodeType(Builder):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('name', 'string'),
                       Attribute('description', 'string')]

    def getByName(cls, name):
        rows = db.query('''SELECT code, description
                           FROM %s WHERE code_str = %s''' % (cls._tableName, `name`)) # ugh. stygg escaping
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (cls.__name__, name))
        row = rows[0]

        id = int(row['code'])
        description = row['description']

        return cls(id, name=name, description=description)

    getByName = classmethod(getByName)

    def _load(self):
        rows = db.query('''SELECT code_str, description
                           FROM %s WHERE code = %s''' % (self._tableName, self._id))
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (self.__class__.__name__, self._id))
        row = rows[0]

        self._name = row['code_str']
        self._description = row['description']

    load_name = load_description = _load

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
        # TODO: legg til OU
        import Account, Disk, Group, Host, Person
        if self.get_name() == 'account':
            return Account.Account
        elif self.get_name() == 'disk':
            return Disk.Disk
        elif self.get_name() == 'group':
            return Group.Group
        elif self.get_name() == 'host':
            return Host.Host
        elif self.get_name() == 'ou':
            raise NotImplementedError('OU is not implemented')
        elif self.get_name('person'):
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

class QuarantineType(CodeType):
    _tableName = 'quarantine_code'

class Spread(CodeType):
    _tableName = 'spread_code'
