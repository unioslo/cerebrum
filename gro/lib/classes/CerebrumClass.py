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

import Database
from GroBuilder import GroBuilder
from Builder import Attribute
from Searchable import Searchable


__all__ = ['CerebrumAttr', 'CerebrumEntityAttr', 'CerebrumClass']

class CerebrumAttr(Attribute):
    def __init__(self, name, data_type, cerebrum_name=None,
                 write=False, from_cerebrum=None, to_cerebrum=None):
        Attribute.__init__(self, name, data_type, write=write)

        self.cerebrum_name = cerebrum_name or name
        if to_cerebrum is not None:
            self.to_cerebrum = to_cerebrum
        if from_cerebrum is not None:
            self.from_cerebrum = from_cerebrum

        assert type(self.cerebrum_name) == str

    def to_cerebrum(self, value):
        return value

    def from_cerebrum(self, value):
        return value

class CerebrumEntityAttr(CerebrumAttr):
    def __init__(self, name, data_type, entity_class, cerebrum_name=None, write=False):
        CerebrumAttr.__init__(self, name, data_type, cerebrum_name, write)
        self.entity_class = entity_class
    def to_cerebrum(self, value):
        return value.get_entity_id()

    def from_cerebrum(self, value):
        return self.entity_class(int(value))

class CerebrumTypeAttr(CerebrumAttr):
    def __init__(self, name, data_type, type_class, cerebrum_name=None, write=False):
        CerebrumAttr.__init__(self, name, data_type, cerebrum_name, write)
        self.type_class = type_class

    def to_cerebrum(self, value):
        return value.get_id()

    def from_cerebrum(self, value):
        return self.type_class(id=int(value))

class CerebrumClass(Searchable):
    cerebrum_class = None

    def _load_cerebrum(self):
        e = self.cerebrum_class(self.get_database())
        e.find(self.get_entity_id())

        for attr in self.slots:
            if not isinstance(attr, CerebrumAttr):
                continue
            value = getattr(e, attr.cerebrum_name)
            if attr.data_type == 'long':
                value = int(value)

            value = attr.from_cerebrum(value)
            setattr(self, '_' + attr.name, value)

    def _save_cerebrum(self):
        e = self.cerebrum_class(self.get_database())
        e.find(self.get_entity_id())

        for attr in self.slots:
            if not isinstance(attr, CerebrumAttr):
                continue
            if not attr.write:
                continue
            value = getattr(self, '_' + attr.name)
            value = attr.to_cerebrum(value)
            setattr(e, attr.cerebrum_name, value)

        e.write_db()

    def build_methods(cls):
        for i in cls.slots:
            setattr(cls, 'load_' + i.name, cls._load_cerebrum)
        for i in cls.slots:
            setattr(cls, 'save_' + i.name, cls._save_cerebrum)

    build_methods = classmethod(build_methods)
    
    def create_search_method(cls):
        """
        This function creates a search method for a search class, using
        the slots convention of the AP API. The generated method calls search()
        on the Cerebrum API class which the search class represents, and returns
        populated AP objects from the results.
        """
        def search(self, **args):
            obj = cls.cerebrum_class(Database.get_database())
            rows = obj.search(**args)
            objects = []

            for row in rows:
                try:
                    entity_id = int(row[0])
                except TypeError:
                    raise Errors.SearchError( 
                        'Could not fetch the ID of one of the found objects.')
                objects.append(cls(entity_id))
                
            return objects
        return search

    create_search_method = classmethod(create_search_method)

# arch-tag: a7da5f91-4f75-4ca1-b086-61f070bb15b3
