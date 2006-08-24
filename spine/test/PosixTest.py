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
        self.pid = []
        self.aid = []
        self.gid = []
        self.session = spine.login(username, password)

    def tearDown(self):
        """Make sure we remove all our test entries from the db."""
        self.__delete_entity('get_account', self.aid)
        self.__delete_entity('get_group', self.gid)
        self.__delete_entity('get_person', self.pid)
        self.session.logout()

    def __delete_entity(self, func, ids):
        for id in ids:
            try:
                tr = self.session.new_transaction()
                get_entity = getattr(tr, func)
                e = get_entity(id)
                if hasattr(e, 'is_posix') and e.is_posix():
                    e.demote_posix()
                e.delete()
                tr.commit()
            except Spine.Errors.NotFoundError:
                pass

    def __create_person(self, tr):
        cmds = tr.get_commands()
        date = cmds.get_date_now()
        gender = tr.get_gender_type('M')
        source = tr.get_source_system('Manual')
        fn = "unit_%s" % id(self)
        ln = "test_%s" % id(self)
        person = cmds.create_person(date, gender, fn, ln, source)
        self.pid.append(person.get_id())
        return person

    def __create_group(self, tr):
        name = 'unittest_gr%s' % id(self)
        group = tr.get_commands().create_group(name)
        self.gid.append(group.get_id())
        return group, name

    def __create_account(self, tr):
        owner = self.__create_person(tr)
        date = tr.get_commands().get_date_none()
        name = 'unittest_ac%s' % id(self)
        account = tr.get_commands().create_account(name, owner, date)
        self.aid.append(account.get_id())
        return account, name
   
    def __join_posix_group(self, tr, account):
        """Adds a posix group to an account, so we can promote it."""
        group, name = self.__create_group(tr)
        group.promote_posix()
        operation = tr.get_group_member_operation_type("union")
        group.add_member(account, operation)
        return group

    def __leave_posix_group(self, tr, account):
        for group in account.get_groups():
            group.remove_member(account)
        
        
    def __get_posix_shell(self, tr):
        shells = tr.get_posix_shell_searcher().search()
        if not shells:
            print >> log, 'Note: No PosixShells in the database, test aborted.'
            return
        else:
            return shells
        
    def ftestDeadlock(self):
        tr = self.session.new_transaction()
        account, name = self.__create_account(tr)
        assert name == account.get_name()
        assert account.is_posix() == False
        
        group = self.__join_posix_group(tr, account)
        gid = group.get_id()
        shells = self.__get_posix_shell(tr)
        shell_name = shells[0].get_name()
        
        uid = tr.get_commands().get_free_uid()
        account.promote_posix(uid, group, shells[0])
        tr.commit()

        tr = self.session.new_transaction()
        account = tr.get_commands().get_account_by_name(name)
        assert account.is_posix() == True
        assert account.get_posix_uid() != None
        assert account.get_shell().get_name() == shell_name
        assert account.get_primary_group().get_id() == gid

        account.demote_posix()
        group.remove_member(account)
        group.demote_posix()
        group.delete()
        account.delete()
        tr.commit()


    def testPromoteAccount(self):
        tr = self.session.new_transaction()
        account, name = self.__create_account(tr)
        aid = account.get_id()

        assert name == account.get_name()
        assert account.is_posix() == False
        
        group = self.__join_posix_group(tr, account)
        gid = group.get_id()
        shells = self.__get_posix_shell(tr)
        shell_name = shells[0].get_name()
        
        uid = tr.get_commands().get_free_uid()
        account.promote_posix(uid, group, shells[0])
        tr.commit()

        tr = self.session.new_transaction()
        op = tr.get_group_member_operation_type("union")
        account = tr.get_account(aid)
        group = tr.get_group(gid)
        assert account.is_posix() == True
        assert account.get_posix_uid() != None
        assert account.get_shell().get_name() == shell_name
        assert account.get_primary_group().get_id() == gid
        account.demote_posix()

        group_member = tr.get_group_member(group, op, account, account.get_type())
        group.remove_member(group_member)
        group.demote_posix()
        group.delete()
        account.delete()
        tr.commit()

    def testDemoteAccount(self):
        tr = self.session.new_transaction()
        account, name = self.__create_account(tr)
        assert name == account.get_name()
        assert account.is_posix() == False
        
        group = self.__join_posix_group(tr, account)
        shells = self.__get_posix_shell(tr)

        if not shells:
            return
        
        uid = tr.get_commands().get_free_uid()
        account.promote_posix(uid, group, shells[0])
        account.demote_posix()
        assert account.is_posix() == False
    
        tr.rollback()
    
    def testPromoteGroup(self):
        tr = self.session.new_transaction()
        group, groupname = self.__create_group(tr)
        assert group.is_posix() == False
        group.promote_posix()
        tr.commit()
        tr = self.session.new_transaction()
        group = tr.get_commands().get_group_by_name(groupname)
        assert group.get_posix_gid() != -1
        assert group.is_posix() == True
        group.demote_posix()
        group.delete()
        tr.commit()

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
