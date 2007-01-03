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
import SpineIDL


class CreateDeleteTest(unittest.TestCase):
    """Tests create and delete for entity classes in Spine."""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def testGroup(self):
        tr = self.session.new_transaction()
        name = 'test%s' % str(id(self))[2:6]
        group = tr.get_commands().create_group(name)
        assert name == group.get_name()
        group.delete()
        self.assertRaises(SpineIDL.Errors.ObjectDeletedError, group.get_name)

        tr.rollback()

    def __create_person(self, transaction):
        commands = transaction.get_commands()
        date = commands.get_date_now()
        gender = transaction.get_gender_type('M')
        source = transaction.get_source_system('Manual')
        first_name = 'unit'
        last_name  = 'test%s' % id(self)
        full_name = '%s %s' % (first_name, last_name)
        return commands.create_person(date, gender, first_name, last_name, source), full_name

    def testPerson(self):
        tr = self.session.new_transaction()
        person, name = self.__create_person(tr)
        assert name == person.get_cached_full_name()
        person.delete()
        self.assertRaises(SpineIDL.Errors.ObjectDeletedError, person.get_cached_full_name)

        tr.rollback()

    def testAccount(self):
        tr = self.session.new_transaction()
        owner, ownername = self.__create_person(tr)
        expire_date = tr.get_commands().get_date_now()
        name = 'test%s' % str(id(self))[2:6]
        account = tr.get_commands().create_account(name, owner, expire_date)
        assert name == account.get_name()
        account.delete()
        self.assertRaises(SpineIDL.Errors.ObjectDeletedError, account.get_name)

        tr.rollback()

    def testOU(self):
        tr = self.session.new_transaction()
        name = 'unittest%s' % id(tr)
        c = tr.get_commands()
        try:
            ou = c.create_ou(name)
        except TypeError:
                ou = c.create_ou(name, 1, 1, 1, 1) # For the stedkode mixin
        assert name == ou.get_name()
        ou.delete()
        self.assertRaises(SpineIDL.Errors.ObjectDeletedError, ou.get_name)

        tr.rollback()

    def __create_host(self, transaction):
        name = 'unittest%s.ntnu.no' % id(self)
        return transaction.get_commands().create_host(name, name), name

    def testHost(self):
        tr = self.session.new_transaction()

        host, name = self.__create_host(tr)
        assert host.get_name() == name
        assert host.get_description() == name
        host.delete()
        self.assertRaises(SpineIDL.Errors.ObjectDeletedError, host.get_name)

        tr.rollback()

    def testDisk(self):
        tr = self.session.new_transaction()

        host, hostname = self.__create_host(tr)
        name = 'test%s' % str(id(self))[2:6]

        disk = tr.get_commands().create_disk(host, name, name)
        assert disk.get_host().get_id() == host.get_id()
        assert disk.get_host().get_name() == host.get_name()
        assert disk.get_path() == name
        assert disk.get_description() == name

        tr.rollback()

if __name__ == '__main__':
    unittest.main()

# arch-tag: 5c4bbf70-eda0-11d9-9432-bc181814ed28
