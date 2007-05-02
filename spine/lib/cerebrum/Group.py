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

import cereconf
import Cerebrum.Database
from Cerebrum.Utils import Factory
from SpineLib.Builder import Attribute
from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.Date import Date
from SpineLib.SpineExceptions import NotFoundError, TooManyMatchesError
from SpineLib.SpineExceptions import ValueError

from CerebrumClass import CerebrumAttr, CerebrumDbAttr
from Cerebrum.Utils import Factory

from OU import OU
from Entity import Entity, ValueDomainHack
from Types import EntityType, GroupVisibilityType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Group']

table = 'group_info'

from SpineLib.DumpClass import Any

class Group(Entity):
    slots = Entity.slots + (
        CerebrumDbAttr('description', table, str, write=True),
        CerebrumDbAttr('visibility', table, GroupVisibilityType, write=True),
        CerebrumDbAttr('creator', table, Entity),
        CerebrumDbAttr('create_date', table, Date),
        CerebrumDbAttr('expire_date', table, Date, write=True),
        CerebrumDbAttr('name', 'entity_name', str, write=True)
    )

    def test(self, n):
        return [1,2,3,4,'asdf', {'1':12321}, ('asdf', 'fdas')] * n
    test.signature = Any
    test.signature_name = 'test'
    test.signature_args = [int]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'group_id',
        'creator':'creator_id'
    }
    db_constants = Entity.db_constants.copy()
    db_constants['entity_name'] = ValueDomainHack('group')

    cerebrum_attr_aliases = {'name':'group_name'}
    cerebrum_class = Factory.get('Group')

    entity_type = 'group'

## Group is registered in PosixGroup
#registry.register_class(Group)

def create_ou_group(self, name):
    db = self.get_database()
    try:
        new_id = Group._create(db, db.change_by, GroupVisibilityType(db, name='A').get_id(), name)
    except Cerebrum.Database.IntegrityError:
        raise ValueError('The given group name could not be created.')
    return Group(db, new_id)
create_ou_group.signature = Group
create_ou_group.signature_name = 'create_group'
create_ou_group.signature_exceptions = [ValueError]
create_ou_group.signature_args = [str]
create_ou_group.signature_write = True
OU.register_methods([create_ou_group])

def create_group(self, name):
    db = self.get_database()
    try:
        new_id = Group._create(db, db.change_by, GroupVisibilityType(db, name='A').get_id(), name)
    except Cerebrum.Database.IntegrityError:
        raise ValueError('The given group name could not be created.')
    return Group(db, new_id)

create_group.signature = Group
create_group.signature_exceptions = [ValueError]
create_group.signature_args = [str]
create_group.signature_write = True
Commands.register_methods([create_group])

def get_group_by_name(self, name):
    """
    Get a group by name.
    \\param name The name of the group to get.
    \\return The Group object with the given name.
    """

    db = self.get_database()

    s = registry.EntityNameSearcher(db)
    value_domain = cereconf.ENTITY_TYPE_NAMESPACE['group']
    s.set_value_domain(registry.ValueDomain(db, name=value_domain))
    s.set_name(name)

    groups = s.search()
    if len(groups) == 0:
        raise NotFoundError('There are no groups with the name %s' % name)
    elif len(groups) > 1:
        raise TooManyMatchesError('There are several groups with the name %s' % name)
    return groups[0].get_entity()

get_group_by_name.signature = Group
get_group_by_name.signature_args = [str]
get_group_by_name.signature_exceptions = [NotFoundError, TooManyMatchesError]
Commands.register_methods([get_group_by_name])

# arch-tag: 263241fc-0255-4c71-9494-dc13153ad781
