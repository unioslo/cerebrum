#!/usr/bin/python2.2
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

import os
import sys
import re

def validate_address(addr):
    if re.match(r'[a-z0-9][a-z0-9-]*[a-z0-9]@[a-z0-9-]+(\.[a-z0-9]+)+$', addr):
        return True
    raise ValueError

mode, listname, admin = sys.argv[1:]

validate_address(listname)

if mode == 'newlist':
    validate_address(admin)
    cmd = "/local/bin/python bin/newlist -a %s -i %s" % (admin, listname)
elif mode == 'add_admin':
    validate_address(admin)
    cmd = "/local/bin/python bin/change_admins -a %s %s" % (listname, admin)
elif mode == 'rmlist':
    cmd = "/local/bin/python bin/rmlist -a %s" % listname
else:
    raise ValueError

args = ['/local/bin/ssh', 'lister', 'su', '-', 'mailman', '-c',
        "'" + cmd + ">/dev/null'"]
os.execv(args[0], args)
