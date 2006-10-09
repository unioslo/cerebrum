#!/usr/bin/env python

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

import os
import sys
import SpineClient

if len(sys.argv) != 4:
    print "Usage: %s <username> <password> <file.ior>" % sys.argv[0]
    sys.exit(1)

ior_file = sys.argv[3]
tmp_dir = os.path.expanduser('~/tmp')

try:
    spine = SpineClient.SpineClient(ior_file, idl_path=tmp_dir).connect()
except IOError:
    print "Could not read %s; please make sure the file exist."

session = spine.login(sys.argv[1], sys.argv[2])

tr = session.new_transaction()
for f in dir(tr):
    if not f.startswith("_"):
        print f
