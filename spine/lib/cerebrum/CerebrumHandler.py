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

import mx.DateTime

from SpineLib.Builder import Attribute, Method
from SpineLib.SpineClass import SpineClass
from SpineLib.Transaction import Transaction

from Entity import Entity
from Types import CodeType
from Date import Date

from SpineLib import Registry
registry = Registry.get_registry() 

class CerebrumHandler(Transaction, SpineClass):
    primary = [
        Attribute('client', Entity),
        Attribute('id', int)
    ]
    slots = [
        Attribute('time_started', Date),
    ]
    method_slots = [
        Method('rollback', None),
        Method('commit', None)
    ]

    def __init__(self, *args, **vargs):
        if not SpineClass.__init__(self, *args, **vargs):
            Transaction.__init__(self, self.get_client())
        
        # Set the current time to the started Attribute.
        started = self.get_attr('time_started').get_name_private()
        setattr(self, started, Date(mx.DateTime.now()))

def convert_name(name):
    name = list(name)
    name.reverse()
    last = name[0]
    new_name = name[0].lower()
    for i in name[1:]:
        if last.isupper() and i.islower():
            new_name += '_'
            new_name += i.lower()
            last = '_'
        elif last.islower() and i.isupper():
            new_name += i.lower()
            new_name += '_'
            last = '_'
        else:
            new_name += i.lower()
            last = i

    name = list(new_name)
    if name[-1] == '_':
        del name[-1]

    name.reverse()
    return ''.join(name)

for name, cls in registry.map.items():
    method_name = 'get_' + convert_name(name)

    if issubclass(cls, CodeType):
        def blipp(cls):
            def get_method(self, name):
                return cls(name=name)
            return get_method
        m = blipp(cls)
        args = [('name', str)]
    else:
        m = cls
        args = []
        for i in cls.primary:
            args.append((i.name, i.data_type))

    method = Method(method_name, cls, args)
    CerebrumHandler.register_method(method, m)

registry.register_class(CerebrumHandler)

# arch-tag: 79265054-583c-4ead-ae5b-3720b9d72810
