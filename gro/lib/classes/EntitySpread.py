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

from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import EntityType, Spread

import Registry
registry = Registry.get_registry()

__all__ = ['EntitySpread']

table = 'entity_spread'

class EntitySpread(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('entity_type', table, EntityType),
        DatabaseAttr('spread', table, Spread)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntitySpread)

def get_spreads(self):
    s = registry.EntitySpreadSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_spreads', [EntitySpread]), get_spreads)

# arch-tag: 2b120f66-31fc-49db-9b33-6a771be5f96b
