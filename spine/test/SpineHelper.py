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
#

import Spine
import unittest
from test import test_support

def Connection():
    """Returns a new connection to Spine."""
    return Spine.connect()

def Session():
    """Creates a new session using the username and password from the configuration file."""
    spine = Spine.connect()
    user = Spine.config.get('spine', 'username')
    password = Spine.config.get('spine', 'password')
    return spine.login(user, password)

def Transaction():
    """Grabs a new session and returns a new transaction."""
    session = Session()
    return session.new_transaction()

# arch-tag: 55b61b58-f4d8-42c6-afcf-1c3001d96371
