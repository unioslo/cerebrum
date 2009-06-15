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
from mx.DateTime import DateTimeType
from lib.data import GroupDAO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
import TestData

large_group_id = 149
posix_id = 354983
expired_id = 354981
nonposix_id = 354984
quarantined_id = 354992
notes_id = 354992
spread_id = 354992

class GroupDAOTest(unittest.TestCase):
    """We test against the test-database and we use 4 fabricated groups with 4 fabricated members that have 1 fabricated owners."""

    def test_get_large_group_by_id(self):
        """This was a bootstrap test, but is now used to get a feel for
        the performance of the DAOs."""
        group = GroupDAO.get(large_group_id)
        assert group.id == large_group_id

    def test_posix_group_has_correct_data(self):
        expected = TestData.get_fake_posix_group()

        group = GroupDAO.get(posix_id)

        self.assertEqual(expected, group)

    def test_expired_posix_group_is_expired(self):
        group = GroupDAO.get(expired_id)

        self.assert_(group.is_expired)

    def test_non_posix_group_has_gid_neg1(self):
        group = GroupDAO.get(nonposix_id)

        self.assertEqual(-1, group.posix_gid)
        self.assertFalse(group.is_posix)

    def test_quarantines(self):
        group = GroupDAO.get(quarantined_id)

        for q in group.quarantines:
            self.assert_(q.type_name in ("sperret", "remote", "slutta", "svakt_passord"))
            self.assert_(q.type_description)
            self.assert_(q.description)
            self.assert_(q.creator.id >= 0)
            self.assert_(q.creator.name == "bootstrap_account")
            self.assert_(q.creator.type_name == "account")
            for date in (q.create_date, q.start_date, q.end_date, q.disable_until):
                self.assertValidDate(date)

    def test_notes(self):
        group = GroupDAO.get(notes_id)
        
        for note in group.notes:
            self.assert_(note.id >= 0)
            self.assert_(note.subject)
            self.assert_(note.creator.id >= 0)
            self.assert_(note.creator.name == "bootstrap_account")
            self.assert_(note.creator.type_name == "account")
            self.assertValidDate(note.create_date)
            self.assert_(note.description)

    def test_spreads(self):
        group = GroupDAO.get(spread_id)

        self.assert_(len(group.spreads) == 1)
        for spread in group.spreads:
            self.assert_(spread.name)
            self.assert_(spread.description)

    def test_get_nonexisting_throws_NotFoundException(self):
        self.assertRaises(NotFoundError, GroupDAO.get, -1)

    def assertValidDate(self, date):
        self.assert_(date is None or isinstance(date, DateTimeType))
        
if __name__ == '__main__':
    unittest.main()
