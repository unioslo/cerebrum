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

import Cerebrum.OU
from Cerebrum.extlib import sets
from Cerebrum.Errors import NotFoundError

from server.Cerebrum_core import Errors
from SpineLib.SpineClass import SpineClass
from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from SpineLib import Registry

from Entity import Entity
from Types import EntityType, OUPerspectiveType

registry = Registry.get_registry()

__all__ = ['OU', 'OUStructure']

table = 'ou_info'
class OU(Entity):
    slots = Entity.slots + [
        DatabaseAttr('name', table, str),
        DatabaseAttr('acronym', table, str),
        DatabaseAttr('short_name', table, str), 
        DatabaseAttr('display_name', table, str),
        DatabaseAttr('sort_name', table, str)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id': 'ou_id'
    }
    entity_type = EntityType(name='ou')

registry.register_class(OU)

table = 'ou_structure'

class OUStructure(DatabaseClass):
    primary = [
        DatabaseAttr('ou', table, OU),
        DatabaseAttr('perspective', table, OUPerspectiveType),
    ]
    slots = [DatabaseAttr('parent', table, OU)]
    db_attr_aliases = {
        table : {
            'ou' : 'ou_id',
            'parent' : 'parent_id',
        }
    }

registry.register_class(OUStructure)

def get_parent(self, perspective):
    s = registry.OUStructureSearcher()
    s.set_ou(self)
    return s.search()

OU.register_method(Method('get_parent', OU), get_parent)

def get_children(self, perspective):
    s = registry.OUStructureSearcher()
    s.set_parent(self)
    return s.search()

OU.register_method(Method('get_children', [OU]), get_children)

# arch-tag: ec070b27-28c8-4b51-b1cd-85d14b5e28e4
