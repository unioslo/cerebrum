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

from Builder import Attribute, Method
from GroBuilder import GroBuilder
from Transaction import Transaction

from Entity import Entity
from Types import CodeType

import Registry
registry = Registry.get_registry() 

class APHandler(Transaction, GroBuilder):
    primary = [
        Attribute('client', Entity),
        Attribute('id', int)
    ]
    slots = []
    method_slots = [
        Method('rollback', None),
        Method('commit', None)
    ]

    def __init__(self, *args, **vargs):
        if not GroBuilder.__init__(self, *args, **vargs):
            Transaction.__init__(self, self.get_client())

for name, gro_class in registry.map.items():
    method_name = 'get_' + name[0].lower()
    last = name[0]
    for i in name[1:]:
        if last.islower() and i.isupper():
            method_name += '_'
        last = i
        method_name += i.lower()

    if issubclass(gro_class, CodeType):
        def blipp(gro_class):
            def get_method(self, name):
                return gro_class(name=name)
            return get_method
        m = blipp(gro_class)
        args = [('name', str)]
    else:
        m = gro_class
        args = []
        for i in gro_class.primary:
            args.append((i.name, i.data_type))

    method = Method(method_name, gro_class, args)
    APHandler.register_method(method, m)

registry.register_class(APHandler)

# arch-tag: 042e8f2b-e0fa-4277-9c43-f434f0b3015c
