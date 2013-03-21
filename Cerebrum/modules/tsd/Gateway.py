#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Gateway functionality.

TSD needs to communicate with the gateway, to tell it to open and close access
to project and project members. We do for example need to give project members
access to their project, and hosts for a project needs to set up with proper
routing. All such access is handled by the gateway.

The gateway has an xmlrpc daemon running, which we communicates with. If the
gateway returns exceptions, we can not continue our processes and should
therefor just raise exceptions instead.

"""

# TODO!

import cerebrum_path
import cereconf
from Cerebrum import Errors
