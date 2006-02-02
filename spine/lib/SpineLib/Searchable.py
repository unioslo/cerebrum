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

import copy

from Builder import Method
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
        if not hasattr(self, attr.get_name_private()):
            raise SpineExceptions.ClientProgrammingError('Attribute %s is not set.' % attr.name)
        return getattr(self, attr.get_name_private())
    return get

def create_new_attr(attr, **vargs):
    """Return a copy of the 'attr'.

    Attributes in search-classes should always be writeable.
    To get diffrent methods of comparison, like less or more or like
    inlcude the argument less=True or more=True or like=True.
    """
    new_attr = copy.copy(attr)
    new_attr.write = True
    name = None
    for arg, value in vargs.items():
        if value:
            setattr(new_attr, arg, True)
            name = '_' + arg
    if name:
        if name == '_less' or name == '_more':
            name += '_than'
        new_attr._old_name = new_attr.name
        new_attr.name += name
    return new_attr

def create_set_method(attr):
    """Set the 'value' for the 'attr'.

    Creates a method which sets the value of the 'attr' to 'value'.
    Will only return the set-method if the 'attr' has the exists-
    attribute. Raises an exception if the 'value' is False.
    """
    if getattr(attr, 'exists', False):
        def set(self, value):
            if value is None:
                raise SpineExceptions.ServerProgrammingError('Value %s is not allowed for this method' % value)
            orig = getattr(self, attr.get_name_private(), None)
            if orig is not value:
                setattr(self, attr.get_name_private(), value)
                self.updated.add(attr)

        return set
    else:
        return None


class Searchable(object):
    """Mixin class for adding searchobjects.

    Mixin class which adds generating of searchobjects, which provides
    a complex, but easy to use, API for searching. Classes which
    inherits from this class should implement their own
    create_search_method which should return the search-method.

    In searchobjects you set the values you want to search for, and if
    you want other than direct comparisation, you can use less, more,
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
        search_class.method_slots = ()

        for attr in cls.slots + cls.search_slots:
            if not isinstance(attr, DatabaseAttr):
                continue
            new_attrs = []

            if getattr(attr, 'optional', False):
                new_attr = create_new_attr(attr, exists=True)
                new_attr.data_type = bool
                new_attrs.append(new_attr)

            from Date import Date
            if attr.data_type == str:
                new_attrs.append(create_new_attr(attr, like=True))
            elif attr.data_type in (int, Date):
                new_attrs.append(create_new_attr(attr, less=True))
                new_attrs.append(create_new_attr(attr, more=True))

            
            new_attrs.append(create_new_attr(attr))
            
            # Register original slots and new slots in the searchclass.
            for new_attr in new_attrs:
                new_attr.exceptions += (SpineExceptions.ClientProgrammingError, )
                get = create_get_method(new_attr)
                set = create_set_method(new_attr)
                search_class.register_attribute(new_attr, get=get, set=set, overwrite=True)

        search_class.method_slots += (Method('search', [cls], exceptions=[SpineExceptions.ClientProgrammingError]), )

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
