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

import Cerebrum.Person

from SpineLib.DatabaseClass import DatabaseAttr

from Entity import Entity
from Date import Date
from Types import EntityType, GenderType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Person']

table = 'person_info'
class Person(Entity):
    slots = Entity.slots + [
        DatabaseAttr('export_id', table, str),
        DatabaseAttr('birth_date', table, Date),
        DatabaseAttr('gender', table, GenderType),
        DatabaseAttr('deceased', table, str), # FIXME: gjøre om til bool
        DatabaseAttr('description', table, str)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'person_id'
    }

    entity_type = EntityType(name='person')

registry.register_class(Person)

# arch-tag: 73b26bd2-5c22-455a-bccd-4eb8a03fc9f1
