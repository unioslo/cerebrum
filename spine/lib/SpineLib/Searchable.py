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

import SpineExceptions

__all__ = ['Searchable']

def create_get_method(attr):
    """Returns the value of the variable attr represents.
    
    This function creates a simple get method get(self), which
    uses getattr(). Methods created with this function are used
    in search objects.

    The get method for search objects will raise
    SpineExceptions.ServerProgrammingErrorif the attribute has
    not yet been set.
    """
    def get(self):
        # get the variable
        if not hasattr(self, attr.var_private):
            raise SpineExceptions.ClientProgrammingError('Attribute %s is not set.' % attr.name)
        return getattr(self, attr.var_private)
    get.signature_name = attr.var_get
    get.signature = attr.data_type
    return get

def create_search_attr(attr, modifier=None):
    """Return a copy of the 'attr'.

    Attributes in search-classes should always be writeable.

    Available modifiers are:
    less_than   attr < value
    more_than   attr > value
    like        attr like value
    exists      attr is not null
        or      attr is null

    The modifier will change the name of the attribute.
    attribute fisk with like as modifier will be changed to fisk_like
    """
    assert modifier in (None, 'less_than', 'more_than', 'like', 'exists')

    name = attr.name
    if modifier is not None:
        name += '_' + modifier

    from Builder import Attribute
    new_attr = Attribute(name, attr.data_type, attr.exceptions, True)
    new_attr.modifier = modifier

    return new_attr    

def create_set_method(attr):
    """Set the 'value' for the 'attr'.

    Creates a method which sets the value of the 'attr' to 'value'.
    Will only return the set-method if the 'attr' has the exists-
    attribute. Raises an exception if the 'value' is False.
    """
    # FIXME: denne returnerte None hvis attr hadde exists satt? 20060310 erikgors.
    def set(self, value):
        if value is None:
            raise SpineExceptions.ServerProgrammingError('Value %s is not allowed for this method' % value)
        orig = getattr(self, attr.var_private, None)
        if orig is not value:
            setattr(self, attr.var_private, value)
            self.updated.add(attr)

    set.signature_name = attr.var_set
    set.signature_write = True
    set.signature_args = [attr.data_type]
    set.signature = None
    return set

class Searchable(object):
    """Mixin class for adding searchobjects.

    Mixin class which adds generating of searchobjects, which provides
    a complex, but easy to use, API for searching. Classes which
    inherits from this class should implement their own
    create_search_method which should return the search-method.

    In searchobjects you set the values you want to search for, and if
    you want other than direct comparisation, you can use less_than, more_than,
    like and exists. You can also merge searchobjects, with intersection,
    union or diffrence, if you need to search on serveral types of
    objects.
    """
    search_slots = ()

    def build_search_class(cls):
        from SearchClass import SearchClass
        from DatabaseClass import DatabaseClass, DatabaseAttr

        search_class_name = '%sSearcher' % cls.__name__
        if not hasattr(cls, 'search_class') or search_class_name != cls.search_class.__name__:
        
            exec 'class %s(SearchClass):\n\tpass\ncls.search_class = %s\n' % ( 
                search_class_name, search_class_name)

        search_class = cls.search_class
        search_class.cls = cls

        search_class.slots = ()

        for attr in cls.slots + cls.search_slots:
            if not isinstance(attr, DatabaseAttr):
                continue
            new_attrs = []

            if attr.optional:
                new_attr = create_search_attr(attr, 'exists')
                new_attr.data_type = bool
                new_attrs.append(new_attr)

            from Date import Date
            if attr.data_type == str:
                new_attrs.append(create_search_attr(attr, 'like'))
            elif attr.data_type in (int, Date):
                new_attrs.append(create_search_attr(attr, 'less_than'))
                new_attrs.append(create_search_attr(attr, 'more_than'))
            
            new_attrs.append(create_search_attr(attr))
            
            # Register original slots and new slots in the searchclass.
            for new_attr in new_attrs:
                new_attr.exceptions += (SpineExceptions.ClientProgrammingError, )
                get = create_get_method(new_attr)
                if new_attr.write:
                    set = create_set_method(new_attr)
                else:
                    set = None

                search_class.register_attribute(new_attr, get=get, set=set)

        def search(self):
            return self._search()
        search.signature = [cls]
        search_class.search = search

        cls.search_class = search_class

    build_search_class = classmethod(build_search_class)
    
    def create_search_method(cls):
        """
        This function creates a search(**args) method for the search class, using
        the slots convention of the Spine API.
        """
        raise SpineExceptions.ServerProgrammingError('create_search_method() needs to be implemented in subclass %s.' % cls.__name__)

    create_search_method = classmethod(create_search_method)

# arch-tag: 08f6a74c-997c-486c-8a33-5666156c42d6
