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

from __future__ import generators

from GroBuilder import GroBuilder
from Builder import Attribute, Method

def create_get_method(var):
    """
    This function creates a simple get method get(self), which
    uses getattr().
    Methods created with this function are used in search objects.
    """
    assert type(var) == str

    def get(self, default=None):
        # get the variable
        return getattr(self, '_' + var, default)
    return get

def create_id_iterator(start=0):
    while 1:
        yield start
        start += 1

class SearchClass(GroBuilder):
    search_id_iterator = create_id_iterator()

    def __init__(self, search_id=None):
        GroBuilder.__init__(self)

    def save(self):
        pass

    def reset(self):
        pass

    def create_primary_key(cls, search_id=None):
        if search_id is None:
            search_id = cls.search_id_iterator.next()

        return (search_id, )

    create_primary_key = classmethod(create_primary_key)

    def get_alive_slots(self): # FIXME: dårlig navn?
        alive = {}
        mine = object() # make a unique object
        for attr in self.slots:
            val = getattr(self, '_' + attr.name, mine)
            if val is not mine:
                alive[attr.name] = val
        return alive

    def search(self):
        if not hasattr(self, '_result') or self.updated:
            alive = self.get_alive_slots()
            self._result = self._search(**alive)
            self.updated.clear()

        return self._result

class Searchable(object):
    search_slots = []

    def create_search_class(cls):
        search_class_name = '%sSearch' % cls.__name__
        
        exec 'class %s(SearchClass):\n\tpass\nsearch_class = %s\n' % ( 
            search_class_name, search_class_name)
            
        search_class._cls = cls

        search_class.slots = []
        search_class.method_slots = []
        
        for attr in cls.slots + cls.search_slots:
            get = create_get_method(attr.name)

            if hasattr(attr, 'table'):
                import copy
                new_attr = copy.copy(attr)
                new_attr.write = True
            else:
                new_attr = Attribute(attr.name, attr.data_type, write=True)
            search_class.register_attribute(new_attr, get=get)
            
        # FIXME: this should use register_method
        search_class._search = cls.create_search_method()
        assert search_class._search
        search_class.method_slots.append(Method('search', '%sSeq' % cls.__name__))

        return search_class

    create_search_class = classmethod(create_search_class)
    
    def create_search_method(cls):
        """
        This function creates a search(**args) method for the search class, using
        the slots convention of the AP API.

        """
        raise NotImplementedError('this needs to be implemented in subclass')

    create_search_method = classmethod(create_search_method)

# arch-tag: 0a04df10-40e7-4b09-bc9e-7ca54eae47ef
