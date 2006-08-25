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
from TestObjects import *
from omniORB import CORBA

class PosixTest(SpineObjectTest):
    """Tests promote/demote of accounts and groups in Spine."""

    def createObject(self): pass
    def deleteObject(self): pass

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

    def testCreateDeletePerson(self):
        p = DummyPerson(self.session)

    def testCreateDeleteGroup(self):
        g = DummyGroup(self.session)

    def testCreateDeleteAccount(self):
        p = DummyPerson(self.session)
        a = DummyAccount(self.session, p)

    def testCreateDeleteAccountWithGroup(self):
        p = DummyPerson(self.session)
        a = DummyAccount(self.session, p)
        g = DummyGroup(self.session)
        g.add_member(a)

    def testPromoteDemoteGroup(self):
        g = DummyGroup(self.session)
        assert g.is_posix() == False
        g.promote_posix()
        assert g.get_posix_gid() != -1
        assert g.is_posix() == True
        g.demote_posix()
        assert g.is_posix() == False
        assert g.get_posix_gid() == -1

    def testPromoteDemoteAccount(self):
        p = DummyPerson(self.session)
        a = DummyAccount(self.session, p)
        g = DummyGroup(self.session)
        assert a.is_posix() == False
        g.promote_posix()
        g.add_member(a)
   #     a.promote_posix(g)
   #     assert a.is_posix() == True
   #     a.demote_posix()
   #     assert a.is_posix() == False
   #     g.demote_posix()

if __name__ == '__main__':
    unittest.main()

# arch-tag: c9944718-f3a0-11d9-8f80-6ca94c3e384f
