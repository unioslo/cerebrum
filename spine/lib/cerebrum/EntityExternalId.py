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

import Cerebrum.Database
import Cerebrum.Entity

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import ClientProgrammingError, NotFoundError, TooManyMatchesError, AlreadyExistsError

from Commands import Commands
from Entity import Entity
from Types import EntityType, EntityExternalIdType, SourceSystem

from SpineLib import Registry
registry = Registry.get_registry()

table = 'entity_external_id'
class EntityExternalId(DatabaseClass):
    primary = (
        DatabaseAttr('external_id', table, str),
        DatabaseAttr('id_type', table, EntityExternalIdType),
        DatabaseAttr('source_system', table, SourceSystem),
    )
    slots = (
        DatabaseAttr('entity', table, Entity),
    )
    db_attr_aliases = {
        table: {
            'entity':'entity_id'
        }
    }
        
registry.register_class(EntityExternalId)

def get_external_id(self, id_type, source_system):
    s = registry.EntityExternalIdSearcher(self.get_database())
    s.set_entity(self)
    s.set_id_type(id_type)
    s.set_source_system(source_system)
    result = s.search()
    if not result:
        raise NotFoundError('There are no external IDs of the given type from the given source system.')
    return result[0].get_external_id()

get_external_id.signature = str
get_external_id.signature_args = [EntityExternalIdType, SourceSystem]
get_external_id.signature_exceptions = [NotFoundError]
Entity.register_methods([get_external_id])

def get_external_ids(self):
    s = registry.EntityExternalIdSearcher(self.get_database())
    s.set_entity(self)
    return s.search()
get_external_ids.signature = [EntityExternalId]
Entity.register_methods([get_external_ids])

def set_external_id(self, id, id_type, source_system):
    db = self.get_database()
    # Check if the given ID type is a proper one
    if id_type.get_type().get_id() != self.get_type().get_id():
        raise ClientProgrammingError('The requested external ID type is not for objects of this type.')
    # Check if we already have an ID for this object, and use that if it is found
    s = registry.EntityExternalIdSearcher(db)
    s.set_external_id(id)
    s.set_id_type(id_type)
    s.set_source_system(source_system)
    result = s.search()
    if result:
        ext_id = result[0]
        if ext_id.get_entity().get_id() != self.get_id():
            raise AlreadyExistsError('Another object of the same type has this external ID.')
        # TODO: 2 lines of HACK!
        self.remove_external_id(id_type, source_system)
        return self.set_external_id(id, id_type, source_system)
    else:
        # Get the external ID object from Cerebrum
        e = Cerebrum.Entity.EntityExternalId(db)
        e.find(self.get_id())

        # Check if an external ID already exists for this 
        e.affect_external_id(source_system.get_id(), id_type.get_id())
        e.populate_external_id(source_system.get_id(), id_type.get_id(), id)
        e.write_db()
        return registry.EntityExternalId(self.get_database(), self, id_type, source_system)
set_external_id.signature = EntityExternalId
set_external_id.signature_args = [str, EntityExternalIdType, SourceSystem]
set_external_id.signature_write = True
set_external_id.signature_exceptions = [AlreadyExistsError, ClientProgrammingError]
Entity.register_methods([set_external_id])

def remove_external_id(self, id_type, source_system):
    e = Cerebrum.Entity.EntityExternalId(self.get_database())
    e.find(self.get_id())
    e._delete_external_id(source_system.get_id(), id_type.get_id()) # No need to call write_db(), this executes by itself
remove_external_id.signature = None
remove_external_id.signature_args = [EntityExternalIdType, SourceSystem]
remove_external_id.signature_write = True
Entity.register_methods([remove_external_id])

def get_entity_with_external_id(self, id, id_type, source_system):
    s = registry.EntityExternalIdSearcher(self.get_database())
    s.set_external_id(id)
    s.set_id_type(id_type)
    s.set_source_system(source_system)
    result = s.search()
    if not result:
        raise NotFoundError('No entity with the external ID %s found.' % id)
    return result[0].get_entity()

get_entity_with_external_id.signature = Entity
get_entity_with_external_id.signature_args = [str, EntityExternalIdType, SourceSystem]
get_entity_with_external_id.signature_exceptions = [NotFoundError]
Commands.register_methods([get_entity_with_external_id])

# arch-tag: ee7aa1c8-845b-4ead-89e0-4fc7aa7051b6
