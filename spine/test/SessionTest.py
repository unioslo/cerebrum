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

SPINE_DEFAULT_CHARSET='iso-8859-1'

class SessionTest(unittest.TestCase):
    """Tests the session objects in Spine."""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testSession(self):
        """Test that it is possible to create a self.session and logout successfully."""
        assert len(self.session.get_transactions()) == 0

    def testSetEncoding(self):
        """Test that the default encoding is correct, that it is possible to
        set a new encoding, and that the encoding is set correctly."""
        assert self.session.get_encoding() == SPINE_DEFAULT_CHARSET
        self.session.set_encoding('UTF-8')
        assert self.session.get_encoding() == 'UTF-8'
        self.session.set_encoding('iso-8859-1')
        assert self.session.get_encoding() == 'iso-8859-1'

    def testStringEncoding(self):
        """Checks that the data from Spine is returned using the encoding we
        requested. NOTE: This test does not actually store to the database and
        verify that the data can be fetched correctly from it."""
        self.session.set_encoding('iso-8859-1')
        transaction = self.session.new_transaction()
        ous = transaction.get_ou_searcher().search()
        assert len(ous) >= 1 # We need an OU to perform the test
        ou = ous[0]
        ou.set_name('æøå')
        self.session.set_encoding('UTF-8')
        assert ou.get_name() == 'æøå'.decode('iso-8859-1').encode('UTF-8')
        transaction.rollback()

    def testInvalidEncoding(self):
        """Tests that it is impossible to set an invalid encoding, and that the
        expected exception is raised."""
        self.assertRaises(Spine.Errors.NotFoundError, self.session.set_encoding, 'fisk')

if __name__ == '__main__':
    unittest.main()

# arch-tag: 21cec634-e964-11d9-9061-acc5d1c280b0
