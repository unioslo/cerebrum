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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import EntityType, Spread

from SpineLib import Registry
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
    return [i.get_spread() for i in s.search()]

Entity.register_method(Method('get_spreads', [Spread]), get_spreads)

def add_spread(self, spread):
    obj = self._get_cerebrum_obj()
    obj.add_spread(spread.get_id())
    obj.write_db()

Entity.register_method(Method('add_spread', None, args=[('spread', Spread)], write=True), add_spread)

def delete_spread(self, spread):
    obj = self._get_cerebrum_obj()
    obj.delete_spread(spread.get_id())
    obj.write_db()

Entity.register_method(Method('delete_spread', None, args=[('spread', Spread)], write=True), delete_spread)

# arch-tag: 225423b6-e786-4494-90a1-2b33ba481a92
