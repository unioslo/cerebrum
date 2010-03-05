#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2010 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
disk = Factory.get("Disk")(db)
a = Factory.get("Account")(db)

disks={}
for d in disk.list():
    disks[d['disk_id']]=d

for ho in a.list_account_home():
    if ho['disk_id'] is None:
        for d in disks.values():
            if ho['home'].startswith(d['path']):
                newd=d['disk_id']
                newh=ho['home'][len(d['path']+"/"):]
                a.clear()
                a.find(ho['account_id'])
                print ho['disk_id'],ho['home'],newd,newh
                a.set_homedir(current_id=ho['homedir_id'],
                              disk_id=newd, home=newh)
                a.write_db()
                
