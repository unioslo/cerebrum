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
from Entity import Entity

__all__ = ['OU']

class OU(Entity):
    slots = Entity.slots + [Attribute('name', 'string', writable=True),
                            Attribute('acronym','string',writable=True),
                            Attribute('short_name','string',writable=True),
                            Attribute('display_name','string',writable=True),
                            Attribute('sort_name','string',writable=True)]
    method_slots = Entity.method_slots + [  Method('get_parent', 'OU', 
                                                [Attribute('perspective','string')]
                                            ), 
                                            Method('set_parent', 'void', 
                                                [Attribute('perspective','string'), 
                                                 Attribute('parent','OU')]
                                            ),
                                            Method('unset_parent', 'void', 
                                                [Attribute('perspective','string')]
                                            ),
                                            Method('get_names','stringSeq'), # Actually list of 2-tuples
                                            Method('get_acronyms','stringSeq'), # 2-tuple list as well
                                            Method('get_structure_path', 'string', 
                                                [Attribute('perspective','string')]
                                            ),
                                            Method('get_structure_mappings', 'OUStructureSeq', 
                                                [Attribute('perspective','string')]
                                            ),
                                            Method('list_children', 'OUSeq', 
                                                [Attribute('perspective','string')]
                                            ),
                                            Method('get_children', 'OUSeq', 
                                                [Attribute('perspective','string')]
                                            ), # Alias
                                            Method('root', 'OU'),
                                            Method('get_root', 'OU')
                                         ] # Alias



    cerebrum_class = Cerebrum.OU.OU

    def _load_ou(self):
        e = Cerebrum.OU.OU(Database.get_database())
        e.find(self._entity_id)

        self._name = e.name
        self._acronym = e.acronym
        self._short_name = e.short_name
        self._display_name = e.display_name
        self._sort_name = e.sort_name

    load_name = load_acronym = load_short_name = load_display_name = load_sort_name =_load_ou

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
        return OU(int(e.root()))

    def get_root(self): # Alias for root (I like this better too ;))
        return self.root()

class OUStructure(Builder):
    primary = [Attribute('ou_id', 'long'),
                Attribute('parent_id','long')]
    slots = primary
