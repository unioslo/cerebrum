#!/usr/bin/env python2.2

import unittest

from Cerebrum import Group
from Cerebrum.modules import PosixGroup
from Cerebrum.tests.GroupTestCase import Group_createTestCase

class PosixGroup_createTestCase(Group_createTestCase):

    def setUp(self):
        super(PosixGroup_createTestCase, self).setUp()

        pg = PosixGroup.PosixGroup(self.Cerebrum)
        self._populate_posixgroup(pg)
        pg.write_db()
        self.posixgroup_id = pg.entity_id

    def _populate_posixgroup(self, posixgroup, **args):
        if not args:
            group = Group.Group(self.Cerebrum)
            group.find(self.group_id)
            args = {'parent': group}
        posixgroup.populate(**args)

    def tearDown(self):
        pg = PosixGroup.PosixGroup(self.Cerebrum)
        pg.find(self.posixgroup_id)
        pg.delete()

        super(PosixGroup_createTestCase, self).tearDown()


class PosixGroupTestCase(PosixGroup_createTestCase):
    def testCreatePosixGroup(self):
        self.failIf(getattr(self, 'posixgroup_id', None) is None,
                    "Error: Something wrong in PosixGroup create.")

def suite():
    return unittest.makeSuite(PosixGroupTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
