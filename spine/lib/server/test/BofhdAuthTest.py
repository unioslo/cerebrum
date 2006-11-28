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
from unittest import TestCase, main

from MockDB import *
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthRole, BofhdAuthOpSet, BofhdAuthOpTarget

class TestBofhdAuthOpSet(TestCase):
    def setUp(self):
        self.db = MockDB()
        self.os = BofhdAuthOpSet(self.db)

    def tearDown(self):
        self.db.verify()

    def testInit(self):
        pass

    def testFind(self):
        name = 'test'
        self.db._add_opset(name, [])
        myid = hash(name)
        self.os.find(myid)

    def testFindByName(self):
        name = 'test'
        self.db._add_opset(name, [])
        self.os.find_by_name(name)

    def testWriteDB_not_updated(self):
        self.os.write_db()

    def testWriteDB_updated(self):
        name = 'test'
        self.db._insert_auth_op(name)

        self.os.populate(name)
        self.os.write_db()

    def testDelete(self):
        name = 'test'
        myid = hash(name)
        self.db._add_opset(name, [])
        self.db._delete_auth_op(myid)

        self.os.find(myid)
        self.os.delete()

class TestBofhdAuth(TestCase):
    def setUp(self):
        self.db = MockDB()
        self.db._init_bofhdauth()
        self.ba = BofhdAuth(self.db)

    def tearDown(self):
        self.db.verify()

    def testInit(self):
        pass

    def testNoCaching(self):
        db1 = MockDB()
        db2 = MockDB()
        db1._init_bofhdauth(value_domain=3, method=db1._stub)
        db2._init_bofhdauth(value_domain=4, method=db2._stub)

        # The following methods should not be called, but will be called if ba2
        # uses cached values from ba1.
        db2._stub("""query_1('
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_name]
        WHERE value_domain=:domain AND entity_name=:name', {'domain': 3, 'name': 'bootstrap_group'})""", 19)

        db2._stub("""query_1('
        SELECT gi.description, gi.visibility, gi.creator_id,
               gi.create_date, gi.expire_date, en.entity_name
        FROM [:table schema=cerebrum name=group_info] gi,
             [:table schema=cerebrum name=entity_name] en
        WHERE
          gi.group_id=:g_id AND
          en.entity_id=gi.group_id AND
          en.value_domain=:domain', {'domain': 3, 'g_id': 19})""", ['', MockDB.CONST['visibility'], MockDB.CONST['bootstrap_user'], '2005-09-30', '', 'bootstrap_group'])

        ba1 = BofhdAuth(db1)
        assert ba1.const.group_namespace.int == 3
        ba2 = BofhdAuth(db2)
        assert ba2.const.group_namespace.int == 4, 'cached value!'
        db1.verify()
        db2.verify()

    def testIsSuperUser(self):
        uid = 120
        self.db._superuser(uid)
        assert self.ba.is_superuser(uid)

    def testNoSuperUser(self):
        uid = 120
        self.db._no_superuser()
        self.assertFalse(self.ba.is_superuser(uid))

    def testSuperUser(self):
        uid = 120
        self.db._superuser(uid)
        self.assertTrue(self.ba.is_superuser(uid))

class BofhdAuthOpTargetTest(TestCase):
    def setUp(self):
        self.db = MockDB()
        self.bt = BofhdAuthOpTarget(self.db)

    def tearDown(self):
        self.db.verify()

if __name__ == '__main__':
    main()

# vi:nowrap
