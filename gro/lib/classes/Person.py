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

import Cerebrum.Person

from Builder import Attribute, Method
from CerebrumClass import CerebrumAttr, CerebrumBooleanAttr

from Entity import Entity
from Account import Account
from Types import GenderType

import Registry
registry = Registry.get_registry()

__all__ = ['Person']

class Person(Entity):
    # primaryAccount gir ingen mening
    # name gir bare navnet blant names som er fult navn (:P)
    # affiliations, quarantine med venner må implementeres
    slots = Entity.slots + [
        CerebrumAttr('export_id', str),
        CerebrumAttr('birth_date', str, write=True),
        CerebrumBooleanAttr('deceased', bool, write=True),
        CerebrumAttr('gender', GenderType, write=True),
        CerebrumAttr('description', str, write=True)
    ]

    cerebrum_class = Cerebrum.Person.Person

registry.register_class(Person)

# arch-tag: 73b26bd2-5c22-455a-bccd-4eb8a03fc9f1
