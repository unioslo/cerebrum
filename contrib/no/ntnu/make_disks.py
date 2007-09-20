#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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

# quick fix to create hosts&homedirs. To be extended later on.

import cerebrum_path
from Cerebrum.Utils import Factory

db = Factory.get("Database")()
co = Factory.get("Constants")(db)
host = Factory.get("Host")(db)
disk = Factory.get("Disk")(db)

db.cl_init(change_program="make_disks")

def fix_host(name, desc):
    host.clear()
    try:
        host.find_by_name(name)
        if desc is not None:
            host.description = desc
    except:
        host.populate(name, desc)
    host.write_db()
    return host.entity_id

def fix_disk(path, host_id, desc=''):
    disk.clear()
    try:
        disk.find_by_path(path)
        if desc is not None:
            disk.description = desc
        disk.host_id = host_id
    except:
        disk.populate(host_id, path, desc)
    disk.write_db()

# Todo: parse this from some config file:

jak = fix_host('jak.itea.ntnu.no', 'Homeserver Ansatte')
fix_disk('/home/ahomea', jak)
fix_disk('/home/ahomeb', jak)
fix_disk('/home/ahomec', jak)
fix_disk('/home/ahomed', jak)
fix_disk('/home/ahomee', jak)
fix_disk('/home/ahomef', jak)

bison = fix_host('bison.stud.ntnu.no', 'Homeserver Stud')
fix_disk('/home/shomeo', bison)
fix_disk('/home/shomep', bison)
gaur = fix_host('gaur.stud.ntnu.no', 'Homeserver Stud')
fix_disk('/home/shomeq', gaur)
fix_disk('/home/shomer', gaur)
mammut = fix_host('mammut.stud.ntnu.no', 'Homeserver Stud')
fix_disk('/home/shomes', mammut)
fix_disk('/home/shomet', mammut)

db.commit()
