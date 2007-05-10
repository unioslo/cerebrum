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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import AlreadyExistsError

from Entity import Entity
from Types import EntityType, CodeType
from SpineLib.Date import Date

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityTrait']

table = 'entity_trait_code'
class EntityTraitCode(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str),
        DatabaseAttr('entity_type', table, EntityType),
    )
    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }


table = 'entity_trait'
class EntityTrait(DatabaseClass):
    primary = (
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('code', table, EntityTraitCode),
    )
    slots = (
        DatabaseAttr('entity_type', table, EntityType),
        DatabaseAttr('target', table, Entity, optional=True),
        DatabaseAttr('date', table, Date, optional=True),
        DatabaseAttr('numval', table, int, optional=True),
        DatabaseAttr('strval', table, str, optional=True),
    )
    db_attr_aliases = {
        table: {
            'entity':'entity_id',
            'target': 'target_id'
        }
    }

registry.register_class(EntityTrait)

def add_trait(self, type, target, date, numval, strval):
    db = self.get_database()
    obj = self._get_cerebrum_obj()
    if obj.get_trait(type.get_id()):
        raise AlreadyExistsError('Could not add trait \'%s\', another trait with the same type already exists.' % type.get_name())

    obj.populate_trait(type.get_id(), target, date, numval, strval)
    obj.write_db()
    return EntityTrait(db, self, type)

add_trait.signature = EntityTrait
add_trait.signature_args=[EntityTraitCode, Entity, Date, int, str]
add_trait.signature_write=True
add_trait.signature_exceptions = [AlreadyExistsError]

def remove_trait(self, type):
    db = self.get_database()
    obj = self._get_cerebrum_obj()
    obj.delete_trait(type.get_id())
    obj.write_db()
remove_trait.signature = None
remove_trait.signature_args=[EntityTraitCode]
remove_trait.signature_write=True

def get_trait(self, type):
    s = registry.EntityTraitSearcher(self.get_database())
    s.set_entity(self)
    s.set_trait_type(type)
    return s.search()[0]

def get_traits(self):
    s = registry.EntityTraitSearcher(self.get_database())
    s.set_entity(self)
    return s.search()
get_traits.signature = [EntityTrait]

Entity.register_methods([get_traits, add_trait, remove_trait])

# arch-tag: 04b59b5d-a443-426e-8b3e-743a137b629c
