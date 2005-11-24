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
import Cerebrum.Errors

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import AlreadyExistsError, NotFoundError

from Entity import Entity
from Types import SourceSystem, ContactInfoType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityContactInfo']

table = 'entity_contact_info'

class EntityContactInfo(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('source_system', table, SourceSystem),
        DatabaseAttr('type', table, ContactInfoType),
        DatabaseAttr('preference', table, int)
    ]
    slots = [
        DatabaseAttr('value', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]
    method_slots = []

    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'type' : 'contact_type',
            'preference' : 'contact_pref',
            'value' : 'contact_value',
        }
    }

registry.register_class(EntityContactInfo)

def get_all_contact_info(self):
    s = registry.EntityContactInfoSearcher(self.get_database())
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_all_contact_info', [EntityContactInfo]), get_all_contact_info)

def get_contact_info(self, preference, type, source_system):
    db = self.get_database()
    try:
        return EntityContactInfo(db, self, source_system, type, preference)
    except Cerebrum.Errors.NotFoundError:
        raise Spine.Errors.NotFoundError("No such contact info exists.")

Entity.register_method(Method('get_contact_info', EntityContactInfo, args=[('preference', int), ('type', ContactInfoType), ('source_system', SourceSystem)], exceptions=[NotFoundError]), get_contact_info)

def add_contact_info(self, info, description, preference, contact_type, source_system):
    db = self.get_database()
    entity = Cerebrum.Entity.EntityContactInfo(db)
    entity.find(self.get_id())
    if entity.get_contact_info(source_system.get_id(), contact_type.get_id()):
        raise AlreadyExistsError("This contact info item already exists.")
    entity.add_contact_info(source_system.get_id(), contact_type.get_id(), info, preference, description)
    return EntityContactInfo(db, Entity(db, entity.entity_id), source_system, contact_type, preference)

Entity.register_method(Method('add_contact_info', EntityContactInfo, args=[('info', str),
    ('description', str), ('preference', int), ('contact_type', ContactInfoType),
    ('source_system', SourceSystem)], write=True, exceptions=[AlreadyExistsError]), add_contact_info)

# arch-tag: 955583e8-356a-4422-b7c0-bb843c854157
