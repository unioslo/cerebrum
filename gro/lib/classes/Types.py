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

from DatabaseClass import DatabaseClass, DatabaseAttr

import Registry
registry = Registry.get_registry()

__all__ = []

for name, table in [('EntityType', 'entity_type_code'),
                    ('AddressType', 'address_code'),
                    ('ContactInfoType', 'contact_info_code'),
                    ('GenderType', 'gender_code'),
                    ('SourceSystem', 'source_system'),
                    ('NameType', 'person_name_code'),
                    ('AuthenticationType', 'authentication_code'),
                    ('Spread', 'spread_code'),
                    ('GroupMemberOperationType', 'group_membership_op_code'),
                    ('GroupVisibilityType', 'group_visibility_code'),
                    ('QuarantineType', 'quarantine_code'),
                    ('OUPerspectiveType', 'ou_perspective_code'),
                    ('AuthOperationType', 'auth_op_code'),]:

    exec 'class %s(DatabaseClass):\n pass\ncls=%s' % (name, name)

    cls.primary = [
        DatabaseAttr('id', table, int, dbattr_name='code'),
    ]
    cls.slots = [
        DatabaseAttr('name', table, str, dbattr_name='code_str'),
        DatabaseAttr('description', table, str)
    ]

    registry.register_class(cls)
    __all__.append(name)

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

EntityType.get_class = get_class

# arch-tag: 8c22fbba-ab80-405e-8d56-1e62b7da1cae
