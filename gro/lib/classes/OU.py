# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import Cerebrum.OU
from Cerebrum.Errors import NotFoundError

from Cerebrum.gro.Cerebrum_core import Errors

from Cerebrum.extlib import sets
from GroBuilder import GroBuilder
from Builder import Attribute, Method
from CerebrumClass import CerebrumAttr, CerebrumTypeAttr

import Registry
registry = Registry.get_registry()

Entity = registry.Entity

__all__ = ['OU', 'OUStructure','OUString']

class OU(Entity):
    slots = Entity.slots + [CerebrumAttr('name', 'string', write=True),
                            CerebrumAttr('acronym', 'string', write=True),
                            CerebrumAttr('short_name', 'string', write=True),
                            CerebrumAttr('display_name', 'string', write=True),
                            CerebrumAttr('sort_name', 'string', write=True)]
    method_slots = Entity.method_slots + [Method('get_parent', 'OU', 
                                            [('perspective','OUPerspectiveType')],
                                            ['NotFoundError']),
                                            
                                          Method('set_parent', 'void', [('perspective','OUPerspectiveType'),
                                                                        ('parent','OU')]),
                                          Method('unset_parent', 'void', [('perspective','OUPerspectiveType')]),
                                          Method('get_names','OUStringSeq'),
                                          Method('get_acronyms','OUStringSeq'),
                                          Method('get_structure_path', 'string',
                                                 [('perspective','OUPerspectiveType')]),
                                          Method('get_structure_mappings', 'OUStructureSeq', 
                                                 [('perspective','OUPerspectiveType')]),
                                          Method('list_children', 'OUSeq', 
                                                 [('perspective','OUPerspectiveType')]),
                                          Method('get_children', 'OUSeq', 
                                                 [('perspective','OUPerspectiveType')]), # Alias
                                          Method('root', 'OU'),
                                          Method('get_root', 'OU')] # Alias

    cerebrum_class = Cerebrum.OU.OU

    def get_parent(self, perspective):
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        try:
            parent_id = e.get_parent(perspective.get_id())
        except Cerebrum.Errors.NotFoundError:
            raise Errors.NotFoundError('No parents found in given perspective')
        return OU(int(parent_id))

    def set_parent(self, perspective, parent):
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        e.set_parent(perspective.get_id(), parent.get_entity_id())

    def unset_parent(self, perspective):
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        e.unset_parent(perspective.get_id())

    def get_names(self):
        names = []
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        for name, lang in e.get_names():
            names.append(OUString(name, lang))
        return names

    def get_acronyms(self):
        acronyms = []
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        for acronym, lang in e.get_acronyms():
            acronyms.append(OUString(acronym, lang))
        return acronyms

    def get_structure_path(self, perspective):
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        return e.structure_path(perspective.get_id())

    def get_structure_mappings(self, perspective):
        mappings = []
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        for ou_id, parent_id in e.get_structure_mappings(perspective.get_id()):
            if ou_id is None or parent_id is None: # Skip.. TODO: Is this right?
                continue 
            mappings.append(OUStructure(OU(int(ou_id)), OU(int(parent_id))))
        return mappings

    def list_children(self, perspective): # This differs from the Cerebrum API
        children = []
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        for id in e.list_children(perspective.get_id()):
            children.append(OU(int(id)))
        return children

    def get_children(self, perspective): # Alias for list_children (I like this name more ;))
        return self.list_children(perspective)

    def root(self):
        e = Cerebrum.OU.OU(self.get_database())
        e.entity_id = self.get_entity_id()
        return OU(int(e.root()[0][0]))

    def get_root(self): # Alias for root (I like this better too ;))
        return self.root()

class OUStructure(GroBuilder):
    primary = [Attribute('ou', 'OU'),
                Attribute('parent_ou','OU')]
    slots = primary

class OUString(GroBuilder):
    primary = [Attribute('value', 'string'),
                Attribute('language', 'string')]
    slots = primary

# arch-tag: 47cbce24-9c35-4973-a13d-9fd96f74b917
