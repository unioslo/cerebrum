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

class PosixTest(unittest.TestCase):
    """Tests promote/demote of accounts and groups in Spine."""
    def setUp(self):
        self.session = spine.login(username, password)

    def tearDown(self):
        self.session.logout()

    def __create_person(self, transaction):
        commands = transaction.get_commands()
        date = commands.get_date_now()
        gender = transaction.get_gender_type('M')
        source = transaction.get_source_system('Manual')
        first_name = 'unit'
        last_name  = 'test%s' % id(self)

        return commands.create_person(date, gender, first_name, last_name, source)

    def __create_group(self, tr):
        name = 'unittest_gr%s' % id(self)
        group = tr.get_commands().create_group(name)
        return group, name
    
    def __create_account(self, tr):
        owner = self.__create_person(tr)
        date = tr.get_commands().get_date_none()
        name = 'unittest_ac%s' % id(self)
        account = tr.get_commands().create_account(name, owner, date)

        return account, name
   
    def __join_posix_group(self, tr, account):
        """Adds a posix group to an account, so we can promote it."""
        group, name = self.__create_group(tr)
        group.promote_posix()
        operation = tr.get_group_member_operation_type("union")
        group.add_member(account, operation)
        return group, name
        
    def __get_posix_shell(self, tr):
        shells = tr.get_posix_shell_searcher().search()
        if not shells:
            print >> log, 'Note: No PosixShells in the database, test aborted.'
            return
        else:
            return shells
        
    def testPromoteGroup(self):
        tr = self.session.new_transaction()
        group, name = self.__create_group(tr)
        assert name == group.get_name()
        assert group.is_posix() == False
        group.promote_posix()
        assert group.get_posix_gid() != None
        assert group.is_posix() == True
    
        tr.rollback()

    def testDemoteGroup(self):
        tr = self.session.new_transaction()
        group, name = self.__create_group(tr)
        assert name == group.get_name()
        assert group.is_posix() == False
        
        group.promote_posix()
        group.demote_posix()
        
        assert group.is_posix() == False
        
        tr.rollback()
        
    def testPromoteAccount(self):
        tr = self.session.new_transaction()
        account, name = self.__create_account(tr)
        assert name == account.get_name()
        assert account.is_posix() == False
        
        group = self.__join_posix_group(tr, account)[0]
        shells = self.__get_posix_shell(tr)

        if not shells:
            return
        
        uid = tr.get_commands().get_free_uid()
        account.promote_posix(uid, group, shells[0])
        assert account.get_posix_uid() != None
        assert account.get_shell().get_name() == shells[0].get_name()
        assert account.get_primary_group().get_id() == group.get_id()
        assert account.is_posix() == True
    
        tr.rollback()

    def testDemoteAccount(self):
        tr = self.session.new_transaction()
        account, name = self.__create_account(tr)
        assert name == account.get_name()
        assert account.is_posix() == False
        
        group = self.__join_posix_group(tr, account)[0]
        shells = self.__get_posix_shell(tr)

        if not shells:
            return
        
        uid = tr.get_commands().get_free_uid()
        account.promote_posix(uid, group, shells[0])
        account.demote_posix()
        assert account.is_posix() == False
    
        tr.rollback()
    
if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
