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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseAttr

from Group import Group

from SpineLib import Registry
registry = Registry.get_registry()

import Cerebrum.modules.PosixGroup

Group.register_attribute(DatabaseAttr('posix_gid', 'posix_group', int, optional=True))
Group.db_attr_aliases['posix_group'] = {'id':'group_id'}
Group.build_methods()
Group.build_search_class()

def promote_posix(self):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.PosixGroup.PosixGroup(self.get_database())
    p.populate(parent=obj)
    p.write_db()

Group.register_method(Method('promote_posix', None, write=True), promote_posix)


# arch-tag: 1d1d6cc7-0222-42b1-9e43-4953ad046987
