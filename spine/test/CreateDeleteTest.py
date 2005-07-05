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
from omniORB import CORBA

class CreateDeleteTest(unittest.TestCase):
    """Tests create and delete for entity classes in Spine."""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testGroup(self):
        tr = self.session.new_transaction()
        name = 'unittest%s' % id(self)
        group = tr.get_commands().create_group(name)
        assert name == group.get_name()
        group.delete()
        self.assertRaises(CORBA.OBJECT_NOT_EXIST, group.get_name)

        tr.rollback()

    def __create_person(self, transaction):
        commands = transaction.get_commands()
        date = commands.get_date_now()
        gender = transaction.get_gender_type('M')
        source = transaction.get_source_system('Manual')
        name = 'unittest%s' % id(self)
        return commands.create_person(date, gender, name, source), name

    def testPerson(self):
        tr = self.session.new_transaction()
        person, name = self.__create_person(tr)
        assert name == person.get_cached_full_name()
        person.delete()
        self.assertRaises(CORBA.OBJECT_NOT_EXIST, person.get_cached_full_name)

        tr.rollback()

    def testAccount(self):
        tr = self.session.new_transaction()
        owner, ownername = self.__create_person(tr)
        expire_date = tr.get_commands().get_date_now()
        name = 'unittest%s' % id(self)
        account = tr.get_commands().create_account(name, owner, expire_date)
        assert name == account.get_name()
        account.delete()
        self.assertRaises(CORBA.OBJECT_NOT_EXIST, account.get_name)

        tr.rollback()

    def testOU(self):
        assert 0 # FIXME: someone implement it

    def __create_host(self, transaction):
        name = 'unittest%s' % id(self)
        return transaction.get_commands().create_host(name, name), name

    def testHost(self):
        tr = self.session.new_transaction()

        host, name = self.__create_host(tr)
        assert host.get_name() == name
        assert host.get_description() == name
        host.delete()
        self.assertRaises(CORBA.OBJECT_NOT_EXIST, host.get_name)

        tr.rollback()

    def testDisk(self):
        tr = self.session.new_transaction()

        host, hostname = self.__create_host(tr)
        name = 'unittest%s' % id(self)

        disk = tr.get_commands().create_disk(host, name, name)
        assert disk.get_host().get_id() == host.get_id()
        assert disk.get_host().get_name() == host.get_name()
        assert disk.get_path() == name
        assert disk.get_description() == name

        tr.rollback()

if __name__ == '__main__':
    unittest.main()

# arch-tag: 5c4bbf70-eda0-11d9-9432-bc181814ed28
