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
from TestBase import *
from TestObjects import DummyGroup

class GroupTest(SpineObjectTest):
    def createObject(self):
        self.obj = DummyGroup(self.session)

    def deleteObject(self):
        del self.obj

    def testSetUp(self):
        """ Tests setUp, createObject, tearDown, deleteObject """
        assert 1 

    def testCreate(self):
        """ Verify that the Group gets created properly. """
        assert self.obj
        id = self.obj.get_id()
        assert self.entityExists(id)

    def testPromotePosix(self):
        self.obj.promote_posix()
        assert self.obj.is_posix()

    def testDemotePosix(self):
        self.obj.promote_posix()
        assert self.obj.is_posix()
        self.obj.demote_posix()
        assert not self.obj.is_posix()

    def entityExists(self, id):
        tr = self.session.new_transaction()
        try:
            tr.get_entity(id)
            tr.rollback()
            return True
        except Exception, e:
            tr.rollback()
            return False

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
