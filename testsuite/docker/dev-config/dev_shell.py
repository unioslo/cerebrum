#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules import CLHandler
db = Factory.get('Database')()
cl = CLHandler.CLHandler(db)

db.cl_init(change_program='local-dev')

pu = Factory.get('PosixUser')(db)
ac = Factory.get('Account')(db)
en = Factory.get('Entity')(db)
co = Factory.get('Constants')(db)
gr = Factory.get('Group')(db)
pe = Factory.get('Person')(db)
ou = Factory.get('OU')(db)
di = Factory.get('Disk')(db)
pg = Factory.get('PosixGroup')(db)


def reload_shell():
    global pu
    global ac
    global en
    global co
    global gr
    global pe
    global ou
    global di
    global pg
    pu = Factory.get('PosixUser')(db)
    ac = Factory.get('Account')(db)
    en = Factory.get('Entity')(db)
    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    pe = Factory.get('Person')(db)
    ou = Factory.get('OU')(db)
    di = Factory.get('Disk')(db)
    pg = Factory.get('PosixGroup')(db)