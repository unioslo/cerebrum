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
import Database

from Builder import Attribute, Builder, Method
from CerebrumClass import CerebrumAttr
from Entity import Entity

__all__ = ['OU']

class OU(Entity):
    slots = Entity.slots + [CerebrumAttr('name', 'string', writable=True),
                            CerebrumAttr('acronym', 'string', writable=True),
                            CerebrumAttr('short_name', 'string', writable=True),
                            CerebrumAttr('display_name', 'string', writable=True),
                            CerebrumAttr('sort_name', 'string', writable=True)]
    method_slots = Entity.method_slots + [Method('get_parent', 'OU', [('perspective','string')]), 
                                          Method('set_parent', 'void', [('perspective','string'),
                                                                        ('parent','OU')]),
                                          Method('unset_parent', 'void', [('perspective','string')]),
                                          Method('get_names','stringSeq'), # Actually list of 2-tuples
                                          Method('get_acronyms','stringSeq'), # 2-tuple list as well
                                          Method('get_structure_path', 'string',
                                                 [('perspective','string')]),
                                          Method('get_structure_mappings', 'OUStructureSeq', 
                                                 [('perspective','string')]),
                                          Method('list_children', 'OUSeq', 
                                                 [('perspective','string')]),
                                          Method('get_children', 'OUSeq', 
                                                 [('perspective','string')]), # Alias
                                          Method('root', 'OU'),
                                          Method('get_root', 'OU')] # Alias

    cerebrum_class = Cerebrum.OU.OU

    def get_parent(self, perspective):
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        parent_id = e.get_parent(perspective)
        return OU(int(parent_id))

    def set_parent(self, perspective, parent):
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        e.set_parent(perspective, parent._entity_id)

    def unset_parent(self, perspective):
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        e.unset_parent(perspective)

    def get_names(self):
        names = []
        
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        result = e.get_names()
        
        for name, lang in result:
            names.append((name, lang))
        return names

    def get_acronyms(self):
        acronyms = []
        
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        result = e.get_names()
        
        for acronyms, lang in result:
            acronyms.append((name, lang))
        return acronyms

    def get_structure_path(self, perspective):
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        return e.structure_path(perspective)

    def get_structure_mappings(self, perspective):
        mappings = []
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        for ou_id, parent_id in e.get_structure_mappings(perspective):
            mappings.append(OUStructure(OU(int(ou_id)), OU(int(parent_id))))
        return mappings

    def list_children(self, perspective): # This differs from the Cerebrum API
        children = []
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        for id in e.list_children(perspective):
            children.append(OU(int(id)))
        return children

    def get_children(self, perspective): # Alias for list_children (I like this name more ;))
        return self.list_children(perspective)

    def root(self):
        e = Cerebrum.OU.OU(Database.get_database())
        e.entity_id = self._entity_id
        return OU(int(e.root()[0][0]))

    def get_root(self): # Alias for root (I like this better too ;))
        return self.root()

class OUStructure(Builder):
    primary = [Attribute('ou_id', 'long'),
                Attribute('parent_id','long')]
    slots = primary
