#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

"""

This file is part of the Cerebrum framework.

It generates an text file dump with maillist members.
Suitable for using with maillist systems like mailman(?)
"""


import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email



db = Factory.get('Database')()
ac = Factory.get('Account')(db)
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
g = Factory.get('Group')(db)



# studieprogrammer:
grps = g.search(name='internal:uit.no:fs:186:undenh:*')

for grp in grps:
    grpname = grp['name']
    grp_items = grpname.split(':')

    fname = grp_items[7]  # 7'th item is name of the group. list is zero based

