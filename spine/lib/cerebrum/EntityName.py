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
from Types import ValueDomain

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityName']

table = 'entity_name'

class EntityName(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('value_domain', table, ValueDomain)
    ]
    slots = [
        DatabaseAttr('name', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'name':'entity_name'
        }
    }

registry.register_class(EntityName)

def get_entity_name(self, value_domain):
    s = registry.EntityNameSearcher((self, value_domain))
    s.set_entity(self)
    s.set_value_domain(self)
    (name, ) = s.search()
    return name

m = Method('get_entity_name', EntityName, args=[('value_domain', ValueDomain)])
Entity.register_method(m, get_entity_name)

# arch-tag: 7afc3199-1c56-4142-9895-d3c54d9a58af
