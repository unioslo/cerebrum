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

from Cerebrum.Utils import Factory
import Cerebrum.Errors

from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseAttr, DatabaseError
from CerebrumClass import CerebrumClass, CerebrumAttr, CerebrumDbAttr

from SpineLib import Registry

from Commands import Commands
from Entity import Entity
from Types import EntityType, OUPerspectiveType

registry = Registry.get_registry()

__all__ = ['OU']

table = 'ou_info'
class OU(Entity):
    slots = Entity.slots + [
        CerebrumDbAttr('name', table, str, write=True),
        CerebrumDbAttr('acronym', table, str, write=True),
        CerebrumDbAttr('short_name', table, str, write=True), 
        CerebrumDbAttr('display_name', table, str, write=True),
        CerebrumDbAttr('sort_name', table, str, write=True)
    ]

    method_slots = Entity.method_slots + []

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id': 'ou_id'
    }
    entity_type = EntityType(name='ou')
    cerebrum_class = Factory.get('OU')

registry.register_class(OU)

#def get_structure_mappings(self, perspective):
#    s = registry.OUStructureSearcher()
#    s.set_perspective(perspective)
#    return s.search()
#
#OU.register_method(Method('get_structure_mappings', [registry.OUStructure], args=[('perspective',
#    OUPerspectiveType)]), get_structure_mappings)

def get_parent(self, perspective):
    s = registry.OUStructureSearcher()
    s.set_ou(self)
    s.set_perspective(perspective)
    results = s.search()
    if len(s.search()) > 1:
        raise DatabaseError('More than one parent for %s in perspective %s' % (self, perspective))
    return s.search()[0].get_parent()

OU.register_method(Method('get_parent', OU, args=[('perspective', OUPerspectiveType)],
    exceptions=[DatabaseError]), get_parent)

def get_children(self, perspective):
    s = registry.OUStructureSearcher()
    s.set_parent(self)
    s.set_perspective(perspective)
    return [i.get_ou() for i in s.search()]

OU.register_method(Method('get_children', [OU], args=[('perspective', OUPerspectiveType)]), get_children)

def get_names(self):
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return [i[0] for i in ou.get_names()]

OU.register_method(Method('get_names', [str], args=None, write=False), get_names)

def get_acronyms(self):
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return [i[0] for i in ou.get_acronyms()]

OU.register_method(Method('get_acronyms', [str], args=None, write=False), get_acronyms)

def structure_path(self, perspective):
    ou = Factory.get('OU')(self.get_database())
    ou.find(self.get_id())
    return ou.structure_path(perspective)

OU.register_method(Method('structure_path', str, args=[('perspective', OUPerspectiveType)]),
    structure_path)

def _set_parent(self, parent, perspective, forced_create):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    parent_ou = Factory.get('OU')(db)

    # Create a NULL parent for the parent argument if it does not already have
    # a parent in the given perspective
    if forced_create:
        parent_ou.find(parent.get_id())
        try:
            parent_ou.get_parent(perspective.get_id())
        except Cerebrum.Errors.NotFoundError:
            parent_ou.set_parent(perspective.get_id(), None)

    # Set the parent of the OU
    ou.find(self.get_id())
    # TODO: Catch SQL exception and rethrow a more proper exception
    ou.set_parent(perspective.get_id(), parent.get_id())
    ou.write_db()

def set_parent(self, parent, perspective):
    _set_parent(self, parent, perspective, False)

def set_parent_forced_create(self, parent, perspective):
    _set_parent(self, parent, perspective, True)

OU.register_method(Method('set_parent', None, 
    args=[('parent', OU), ('perspective', OUPerspectiveType)], write=True), set_parent)

OU.register_method(Method('set_parent_forced_create', None, 
    args=[('parent', OU), ('perspective', OUPerspectiveType)], write=True), set_parent_forced_create)

def unset_parent(self, perspective):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    ou.find(self.get_id())
    ou.unset_parent(perspective.get_id())
    ou.write_db()

OU.register_method(Method('unset_parent', None, 
    args=[('perspective', OUPerspectiveType)], write=True), unset_parent)

def create_ou(self, name):
    db = self.get_database()
    ou = Factory.get('OU')(db)
    ou.populate(name)
    ou.write_db()
    spine_ou = OU(ou.entity_id, write_lock=self.get_writelock_holder())
    return spine_ou

Commands.register_method(Method('create_ou', OU, args=[('name', str)], write=True), create_ou)

# arch-tag: ec070b27-28c8-4b51-b1cd-85d14b5e28e4
