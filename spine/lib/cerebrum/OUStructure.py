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

from SpineLib.Builder import Attribute, Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from SpineLib import Registry
from Types import OUPerspectiveType
from OU import OU

registry = Registry.get_registry()

__all__ = ['OUStructure']

table = 'ou_structure'
class OUStructure(DatabaseClass):
    primary = [
        DatabaseAttr('ou', table, OU),
        DatabaseAttr('perspective', table, OUPerspectiveType),
    ]
    slots = [DatabaseAttr('parent', table, OU)]
    db_attr_aliases = {
        table : {
            'ou' : 'ou_id',
            'parent' : 'parent_id',
        }
    }

registry.register_class(OUStructure)

