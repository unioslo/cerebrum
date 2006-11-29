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

from SpineLib.Builder import Attribute
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError
from CerebrumClass import CerebrumClass

from Types import EntityType, ValueDomain
from EntityAuth import EntityAuth
import cereconf

from SpineLib import Registry
registry = Registry.get_registry()

type_cache = {}

class ValueDomainHack(dict):
    def __init__(self, entity_type):
        self.var = cereconf.ENTITY_TYPE_NAMESPACE[entity_type]
        self['value_domain'] = None

    def fix(self):
        var = self.var
        self.var = None
        import Cerebrum.Utils
        db = registry.db or Cerebrum.Utils.Factory.get('Database')()
        self['value_domain'] = ValueDomain(db, name=var).get_id()

        if not type_cache:
            for key, value in db.query('SELECT entity_id, entity_type FROM entity_info'):
                type_cache[int(key)] = int(value)

    def __getitem__(self, key):
        if self.var:
            self.fix()
        return ValueDomain(db, self.var).get_id()

    def items(self):
        if self.var:
            self.fix()
        return dict.items(self)

__all__ = ['Entity']

class Entity(CerebrumClass, DatabaseClass, EntityAuth):
    primary = (
        DatabaseAttr('id', 'entity_info', int),
    )
    slots = (
        DatabaseAttr('type', 'entity_info', EntityType),
    )

    db_attr_aliases = {
        'entity_info': {
            'id':'entity_id',
            'type':'entity_type'
        },
        'entity_name': {
            'id':'entity_id',
            'name':'entity_name'
        }
    }

    entity_type = None

    def __new__(cls, *args, **vargs):
        """Make sure the right class is returned.

        We check to make sure that the correct entity-class is returned.
        
        If the client asks for entity which really is an subclass of
        entity, the subclass is returned.
        """
        obj = super(Entity, cls).__new__(Entity, *args, **vargs)

        # Check if obj is a fresh object
        if obj.__class__ is Entity:
            obj.__init__(*args, **vargs)

        if not hasattr(obj, '_type') and obj.get_id() in type_cache:
            obj._type = EntityType(obj.get_database(), id=type_cache[obj.get_id()])

        # get the correct class for this entity
        entity_type = obj.get_type()
        assert entity_type
        for entity_class in Entity.__subclasses__():
            if not hasattr(entity_class, 'entity_type'):
                continue
            if entity_class.entity_type == entity_type.get_name():
                break
        else:
            entity_class = Entity

        if cls is not entity_class and cls is not Entity:
            raise NotFoundError('Wrong class. Asked for %s, but found %s' % (cls, entity_class))
        else:
            obj.__class__ = entity_class

        return obj

    def delete(self):
        self._delete_from_cerebrum()
        self._delete()
    delete.signature_name = 'delete'
    delete.signature = None
    delete.signature_write = True
    
registry.register_class(Entity)

# arch-tag: 2004ac4b-14d6-4f9b-93a2-e255c5a0d3f8
