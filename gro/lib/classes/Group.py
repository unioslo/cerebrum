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

import Cerebrum.Group

from CerebrumClass import CerebrumAttr

from Entity import Entity
from Types import GroupVisibilityType
from Date import Date

import Registry
registry = Registry.get_registry()

__all__ = ['Group']

class Group(Entity):
    corba_parents = [Entity]
    slots = Entity.slots + [
        CerebrumAttr('name', str, 'group_name', write=True),
        CerebrumAttr('description', str, write=True),
        CerebrumAttr('visibility', GroupVisibilityType, write=True),
        CerebrumAttr('expire_date', Date, write=True)
    ]

    cerebrum_class = Cerebrum.Group.Group

registry.register_class(Group)

# arch-tag: e485b7a1-290b-467a-a746-761c30b71e13
