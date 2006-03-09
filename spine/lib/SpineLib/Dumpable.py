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

from Builder import Attribute

from Cerebrum.extlib.sets import Set
from SpineExceptions import ClientProgrammingError

__all__ = ['Dumpable']

def create_mark_method(name, method_name, optional=False, attr=None):
    """
    This function creates a mark method for every attribute and read method in the class.
    Using mark_<something> marks <something> for inclusion in the dump.
    """

    def dump(self):
        for struct, obj in zip(self.structs, self._objects):
            if optional:
                struct['%s_exists' % name] = True
            try:
                value = getattr(obj, method_name)()
                struct[name] = value
            except Exception, e:
                if optional:
                    struct['%s_exists' % name] = False
                else:
                    raise e

    return dump

class Dumpable(object):
    """Mixin class for adding dumperobjects.
    
    Mixin class which adds generating of dumperobjects, which can be
    used to read many attributes/methods in one method-call.

    The new generated class has methods for marking which attributes and
    methods you want returned, and can then be asked to return them all
    at once, in structs.
    """
    
    def build_dumper_class(cls):
        from DumpClass import DumpClass, Struct
        from Searchable import Searchable

        dumper_class_name = '%sDumper' % cls.__name__

        if not hasattr(cls, 'dumper_class') or dumper_class_name != cls.dumper_class.__name__:
        
            exec 'class %s(DumpClass):\n\tpass\ncls.dumper_class = %s\n' % ( 
                dumper_class_name, dumper_class_name)
                
        dumper_class = cls.dumper_class
        
        dumper_class.primary = (Attribute('objects', [cls]),)
        dumper_class.slots = ()
        dumper_class.cls = cls

        # make dump accessable from search classes
        def dump(self):
            return self.structs
        dump.signature = [Struct(cls)]
        dumper_class.dump = dump

        if issubclass(cls, Searchable):
            cls.search_class.get_dumpers = create_get_dumpers()

            cls.search_class.dump =  create_dump(dumper_class)
            dump.signature = [Struct(cls)]

    build_dumper_class = classmethod(build_dumper_class)

def create_get_dumpers():
    def get_dumpers(self):
        objs = []
        data = []
        for i in self.get_search_objects():
            objs.append(i)
            data.append([])
        for rows in self.get_split_rows():
            for i, row in enumerate(rows):
                data[i].append(row)

        return [obj.cls.dumper_class(data, obj.get_signature()) for obj, data in zip(objs, data)]
    from DumpClass import DumpClass
    get_dumpers.signature = [DumpClass]
    return get_dumpers

def create_dump(dumper_class):
    def dump(self):
        dumper = dumper_class(self.get_rows(), self.get_signature())
        return dumper.dump()
    from DumpClass import Struct
    dump.signature = [Struct(dumper_class.cls)]
    return dump

# arch-tag: 94dead40-0291-4725-a4dd-a37303eec825
