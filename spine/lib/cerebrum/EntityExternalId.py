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

import Cerebrum.Entity

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Types import EntityType, EntityExternalIdType, SourceSystem

from SpineLib import Registry
registry = Registry.get_registry()

table = 'entity_external_id'
class EntityExternalId(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('id_type', table, EntityExternalIdType),
        DatabaseAttr('source_system', table, SourceSystem),
    ]
    slots = [
        DatabaseAttr('entity_type', table, EntityType),
        DatabaseAttr('external_id', table, str, write=True)
    ]

    db_attr_aliases = {
        table: {
            'entity':'entity_id'
        }
    }
        
registry.register_class(EntityExternalId)

def get_external_ids(self):
    s = registry.EntityExternalIdSearcher()
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_external_ids', [EntityExternalId]), get_external_ids)

def add_external_id(self, id, id_type, source_system):
    e = Cerebrum.Entity.EntityExternalId(self.get_database())
    e.find(self.get_id())
    e.affect_external_id(source_system.get_id(), id_type.get_id())
    e.populate_external_id(source_system.get_id(), id_type.get_id(), id)
    e.write_db()
    return EntityExternalId(self, id_type, source_system)

Entity.register_method(Method('add_external_id', EntityExternalId, args=[('id', str), ('id_type', EntityExternalIdType), ('source_system', SourceSystem)], write=True), add_external_id)

# arch-tag: ee7aa1c8-845b-4ead-89e0-4fc7aa7051b6
