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

import unittest
from lib.data.HostDAO import HostDAO

class HostDAOTest(unittest.TestCase):
    def test_get_email_hosts(self):
        count = 0
        hosts = HostDAO().get_email_servers()
        for host in hosts:
            count += 1
            self.assert_(host.id)
            self.assert_(host.name)
        self.assert_(count > 0)
    
    def test_get_email_targets(self):
        count = 0
        entity_id = 173691
        targets = HostDAO().get_email_targets(entity_id)
        for target in targets:
            count += 1
            self.assert_(target.id == 217124)
            self.assert_(target.type == "account@emanuel.itea.ntnu.no")
            self.assert_(hasattr(target, 'alias'))
            self.assert_(target.address == "leiv.andenes@ntnu.no")
        self.assert_(count > 0)

    def test_get_email_targets_not_found_gives_empty_list(self):
        entity_id = -1
        targets = HostDAO().get_email_targets(entity_id)
        self.assert_(len(targets) == 0)

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
