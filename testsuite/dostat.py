#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002 University of Oslo, Norway
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

#
# This example shows how one can perform profiling in python
#

import profile
import pstats
import import_SATS

pr = profile.Profile()
pr.calibrate(1000)

pdta = pr.run('import_SATS.main()')

pdta.dump_stats('profile')

s = pstats.Stats('profile')
s.strip_dirs()
s.sort_stats('time').print_stats(20)

# arch-tag: ccb0a8d1-64ce-4e95-9ab2-8a11398a52de
