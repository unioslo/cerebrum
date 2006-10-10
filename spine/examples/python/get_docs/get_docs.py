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

"""
This is an example that fetches the commented IDL source code from Spine.
Comments are in Doxygen format.  It relies on the cached IDL client example.
Make sure PYTHONPATH contains the path to SpineClient.py and that
SpineCore.idl is in the same directory as SpineClient.py.
"""

import os, sys
import SpineClient

if len(sys.argv) != 2:
    print "Usage: %s <file.ior>" % sys.argv[0]
    sys.exit(1)

ior_file = sys.argv[1]
tmp_dir = os.path.expanduser('~/tmp')

print 'Connecting to Spine...'
spine = SpineClient.SpineClient(ior_file, idl_path=tmp_dir).connect()
print 'Fetching commented IDL source...'
src = spine.get_idl_commented()
print 'Saving...'
f = open('commented.idl', 'w')
f.write(src)
f.close()
print 'Done!'

# arch-tag: 83bf6634-e7d7-11d9-8f72-cb1ef6981e96
