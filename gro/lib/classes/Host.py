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

import Cerebrum.Disk # er det ikke logisk at Host ligger i Disk? :p

from CerebrumClass import CerebrumAttr

import Registry
registry = Registry.get_registry()

Entity = registry.Entity

__all__ = ['Host']

class Host(Entity):
    slots = Entity.slots + [CerebrumAttr('name', 'string', write=True), 
                            CerebrumAttr('description', 'string', write=True)]

    cerebrum_class = Cerebrum.Disk.Host

# arch-tag: 8351c2b3-4238-447d-b168-3e396a9d2646
