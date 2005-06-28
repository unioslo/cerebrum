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
"""

import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../cached_idl/'))
import Spine

print 'Connecting to Spine...'
c = Spine.connect()
print 'Fetching commented IDL source...'
src = c.get_idl_commented()
print 'Saving...'
f = open('commented.idl', 'w')
f.write(src)
f.close()
print 'Done!'
