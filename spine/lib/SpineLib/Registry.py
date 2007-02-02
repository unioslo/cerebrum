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

from Builder import Builder
from Searchable import Searchable
from Dumpable import Dumpable
from SpineExceptions import ServerProgrammingError

class Registry(object):
    def __init__(self):
        self.map = {}
        self.classes = []

    def register_class(self, cls):
        name = cls.__name__
        public = getattr(cls, 'signature_public', False)

        if issubclass(cls, Builder):
            cls.build_methods()

            if issubclass(cls, Searchable):
                cls.build_search_class()
                if public:
                    cls.search_class.signature_public = public
                self.register_class(cls.search_class)

            if issubclass(cls, Dumpable):
                cls.build_dumper_class()
                if public:
                    cls.dumper_class.signature_public = public
                self.register_class(cls.dumper_class)

        if name in self.map:
            # Nothing wrong with registering the same class twice,
            # but we do not support different classes with the same
            # name.
            assert self.map[name] == cls, """
                Fatal Error: Conflicting names (%s != %s)""" % ( self.map[name], cls)
        else:
            self.classes.append(cls)

        self.map[name] = cls

    def __getattr__(self, key):
        if not key in self.map:
            raise ServerProgrammingError('Class %s is not in the Spine registry.' % key)
        return self.map[key]

    def build_all(self):
        for i in self.classes:
            i.build_methods()

_registry = None
def get_registry():
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry

# arch-tag: 3d88e0d4-1147-4562-a8fa-1a627e2ced49
