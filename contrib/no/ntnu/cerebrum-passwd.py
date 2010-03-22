#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

import cerebrum_path
import getopt
from Cerebrum.Utils import Factory
from getpass import getpass
import sys

db=Factory.get("Database")()
db.cl_init(change_program="set_password")
ac=Factory.get("Account")(db)

opts,args = getopt.getopt(sys.argv[1:], 'a')

set_admin_password = False
for opt, val in opts:
    if opt=='-a':
        set_admin_password=True

user = args[0]

ac.find_by_name(user)

pass1 = getpass("Password:")
pass2 = getpass("Repeat password:")

assert pass1 == pass2

if set_admin_password:
    ac.set_admin_password(pass1)
else:
    ac.set_password(pass1)

ac.write_db()
db.commit()
