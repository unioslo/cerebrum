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
from Types import SourceSystem, AddressType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityAddress']

table = 'entity_address'

# TODO: country

class EntityAddress(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table,  Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('address_type', table, AddressType),
    ]
    slots = [
        DatabaseAttr('address_text', table, str, write=True), 
        DatabaseAttr('p_o_box', table, str, write=True),
        DatabaseAttr('postal_number', table, str, write=True),
        DatabaseAttr('city', table, str, write=True),
        DatabaseAttr('country', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{'entity':'entity_id'}
    }

registry.register_class(EntityAddress)

def get_addresses(self):
    s = registry.EntityAddressSearch(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_addresses', [EntityAddress]), get_addresses)

# arch-tag: 28c9c7fa-3191-4c48-b48c-e0f63c796f43
