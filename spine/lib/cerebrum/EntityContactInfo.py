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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import AlreadyExistsError

from Entity import Entity
from Person import Person
from OU import OU
from Types import SourceSystem, ContactInfoType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityContactInfo']

table = 'entity_contact_info'

class EntityContactInfo(DatabaseClass):
    primary = (
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('type', table, ContactInfoType),
        DatabaseAttr('preference', table, int)
    )
    slots = (
        DatabaseAttr('value', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    )
    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'type' : 'contact_type',
            'preference' : 'contact_pref',
            'value' : 'contact_value',
        }
    }

    def get_auth_entity(self):
        return self.get_entity()
    get_auth_entity.signature = Entity
registry.register_class(EntityContactInfo)

def remove_contact_info(self, source, type, pref):
    """Remove contact info from entity."""
    obj = self._get_cerebrum_obj()
    obj.delete_contact_info(source.get_id(), type.get_id(), pref)

remove_contact_info.signature = None
remove_contact_info.signature_write = True
remove_contact_info.signature_args = [SourceSystem, ContactInfoType, int]

def add_contact_info(self, source, type, value, pref, description):
    """Add a contact info to entity."""
    db = self.get_database()
    entity = Cerebrum.Entity.EntityContactInfo(db)
    entity.find(self.get_id())
    
    # Check if this contact info with this preference already exists.
    infos = entity.get_contact_info(source.get_id(), type.get_id())
    preferences = [i[3] for i in infos]
    if pref in preferences:
        raise AlreadyExistsError("This contact info item already exists.")
    
    entity.add_contact_info(source.get_id(), type.get_id(), value, pref, description)

add_contact_info.signature = None
add_contact_info.signature_write = True
add_contact_info.signature_args = [SourceSystem, ContactInfoType, str, int, str]

def get_all_contact_info(self):
    """Returns all contact info on this entity."""
    s = registry.EntityContactInfoSearcher(self.get_database())
    s.set_entity(self)

    # Sorted the way it should be presented to the user,
    # with highest preference in each type on top.
    s.order_by(s, 'type')
    s.order_by_desc(s, 'preference')
    
    return s.search()

get_all_contact_info.signature = [EntityContactInfo]

def get_contact_info(self, source, type, pref):
    """Returns a specific contact info based on given criteriums."""
    return EntityContactInfo(self.get_database(), self, source, type, pref)

get_contact_info.signature = EntityContactInfo
get_contact_info.signature_args = [SourceSystem, ContactInfoType, int]


methods = [add_contact_info, remove_contact_info,
           get_contact_info, get_all_contact_info]
OU.register_methods(methods)
Person.register_methods(methods)

# arch-tag: 955583e8-356a-4422-b7c0-bb843c854157
