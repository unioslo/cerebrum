# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['CodeType']

class CodeType(DatabaseClass):
    def create_primary_key(cls, id=None, name=None, **args):
        if id is None and name is not None:
            s = cls.search_class(name)
            s.set_name(name)
            (obj,) = s.search()
            id = obj.get_id()

        assert type(id) in (int, long)

        return super(CodeType, cls).create_primary_key(id, name, **args)

    create_primary_key = classmethod(create_primary_key)

for name, table in [('AccountType', 'account_code'),
                    ('EntityType', 'entity_type_code'),
                    ('AddressType', 'address_code'),
                    ('ContactInfoType', 'contact_info_code'),
                    ('GenderType', 'gender_code'),
                    ('SourceSystem', 'authoritative_system_code'),
                    ('NameType', 'person_name_code'),
                    ('AuthenticationType', 'authentication_code'),
                    ('Spread', 'spread_code'),
                    ('Flag', 'flag_code'),
                    ('GroupMemberOperationType', 'group_membership_op_code'),
                    ('GroupVisibilityType', 'group_visibility_code'),
                    ('QuarantineType', 'quarantine_code'),
                    ('OUPerspectiveType', 'ou_perspective_code'),
                    ('AuthOperationType', 'auth_op_code'),
                    ('HomeStatus', 'home_status_code'),
                    ('PersonExternalIdType', 'person_external_id_code'),
                    ('ValueDomain', 'value_domain_code')]:

    exec 'class %s(CodeType):\n pass\ncls=%s' % (name, name)

    cls.primary = [
        DatabaseAttr('id', table, int),
    ]
    cls.slots = [
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    ]
    cls.db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }
            

    registry.register_class(cls)
    __all__.append(name)

# arch-tag: 965b1b0a-4526-4189-b507-2459e1ed646d
