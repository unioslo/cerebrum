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

import copy

from Builder import Method

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

class Searchable(object):
    search_slots = []

    def build_search_class(cls):
        from SearchClass import SearchClass

        search_class_name = '%sSearch' % cls.__name__
        if not hasattr(cls, 'search_class') or search_class_name != cls.search_class.__name__:
        
            exec 'class %s(SearchClass):\n\tpass\ncls.search_class = %s\n' % ( 
                search_class_name, search_class_name)

        search_class = cls.search_class
            
        search_class._cls = cls

        search_class.slots = SearchClass.slots + []
        search_class.method_slots = SearchClass.method_slots + []

        for attr in cls.slots + cls.search_slots:
            get = create_get_method(attr.name)

            new_attr = copy.copy(attr)
            new_attr.write = True
            search_class.register_attribute(new_attr, get=get, overwrite=True)
            
        search_class._search = cls.create_search_method()
        assert search_class._search
        search_class.method_slots.append(Method('search', cls, sequence=True))

        cls.search_class = search_class

    build_search_class = classmethod(build_search_class)
    
    def create_search_method(cls):
        """
        This function creates a search(**args) method for the search class, using
        the slots convention of the AP API.

        """
        raise NotImplementedError('this needs to be implemented in subclass')

    create_search_method = classmethod(create_search_method)

# arch-tag: 0a04df10-40e7-4b09-bc9e-7ca54eae47ef
