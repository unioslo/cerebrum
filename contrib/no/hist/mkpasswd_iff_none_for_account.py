#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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

# Updates an accounts password. Iff no password set, make one.
# TODO: co.auth_type_md5_crypt shoulb be replaced by something.
#       Code for this in bofh_uio_cmds.

import cerebrum_path
import os
import sys
import cereconf

from Cerebrum import Entity
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory

# Set up the basics.
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='mkpasswd')

acc = Account.Account(db)
ent = Entity.Entity(db)

for row in ent.list_all_with_type(co.entity_account):
    acc.clear()
    acc.find(row['entity_id'])
    name = acc.get_account_name()

    try:
        auth = acc.get_account_authentication(co.auth_type_md5_crypt)
        print "Found: %s:%s" % (name, auth) 
    except Errors.NotFoundError:
        pltxt = acc.make_passwd(acc.get_account_name())
        print "Not found: %s, new: %s" % (name,pltxt)
        acc.set_password(pltxt)
        acc.write_db()

db.commit()

# arch-tag: 13430f5e-be96-4c8f-8820-37f6a39538b9
