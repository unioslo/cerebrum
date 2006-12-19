# -*- coding: iso-8859-1 -*-

# Copyright 2004-2006 University of Oslo, Norway
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

import unittest

# Test classes
from AuthTest import *
from AutoTest import *
from CommunicationTest import *
from CreateDeleteTest import *
#from EmailTest import * # Not working.
from LoginTest import * 
from ExtentionTest import *
from HomeDirectoryTest import *
from LockingTest import *
from OUTest import *
from PosixTest import *
from SessionTest import *
from TransactionTest import *
#from DumperTest import * # Untested
#from ExternalIdTest import * # Untested
#from GroupMemberTest import * # Untested
#from GroupTest import * # Untested
#from JoinerTest import * # Untested
#from LockingTest import * # Untested
#from MultipleLoginTest import * # Untested
#from ViewTest import * # Untested

if __name__ == '__main__':
    unittest.main()

# arch-tag: d4e71fa7-90e0-4fd5-8b38-ce5ac0340e2f
