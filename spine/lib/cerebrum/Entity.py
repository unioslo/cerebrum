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

from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Types import EntityType
from EntityAuth import EntityAuth

from SpineLib import Registry
registry = Registry.get_registry()


__all__ = ['Entity']

class Entity(DatabaseClass, EntityAuth):
    primary = [
        DatabaseAttr('id', 'entity_info', int)
    ]
    slots = [
        DatabaseAttr('type', 'entity_info', EntityType)
    ]
    method_slots = []

    db_attr_aliases = {
        'entity_info': {
            'id':'entity_id',
            'type':'entity_type'
        }
    }

    entity_type = None

    def __new__(cls, *args, **vargs):
        obj = super(Entity, cls).__new__(Entity, *args, **vargs)

        # Check if obj is a fresh object
        if obj.__class__ is Entity:
            obj.__init__(*args, **vargs)

        # get the correct class for this entity
        entity_type = obj.get_type()
        for entity_class in Entity.builder_children:
            if entity_class.entity_type is entity_type:
                break
        else:
            entity_class = Entity
            #raise Exception('unknown or not implemented type %s' % entity_type.get_name())

        if cls is not entity_class and cls is not Entity:
            raise Exception('wrong class. Asked for %s, but found %s' % (cls, entity_class))
        else:
            obj.__class__ = entity_class

        return obj

registry.register_class(Entity)

