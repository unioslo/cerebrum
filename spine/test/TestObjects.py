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

class TestEntity(object):
    def __init__(self, session, id=None):
        self._keep = False
        self.session = session
        self.open = False
        self.get_attr = "get_entity"
        if id:
            self.id = id
        else:
            self._create_obj()

    def __del__(self):
        if not self._keep:
            obj = self._get_obj()
            obj.delete()
            self._commit()
        
    def _get_tr(self):
        if not self.open:
            self.tr = self.session.new_transaction()
            self.open = True
        return self.tr

    def _get_obj(self):
        tr = self._get_tr()
        attr = getattr(tr, self.get_attr)
        return attr(self.id)

    def _commit(self):
        if self.open:
            self.open = False
            self.tr.commit()

    def __getattr__(self, attr):
        obj = self._get_obj()
        return getattr(obj, attr)

class DummyPerson(TestEntity):
    def __init__(self, session, id=None):
        super(DummyPerson, self).__init__(session, id)
        self.get_attr = "get_person"

    def __del__(self):
        if not self._keep:
            super(DummyPerson, self).__del__()

    def _create_obj(self):
        tr = self._get_tr()
        cmds = tr.get_commands()
        date = cmds.get_date_now()
        gender = tr.get_gender_type('M')
        source = tr.get_source_system('Manual')
        fn = "unit_%s" % id(self)
        ln = "test_%s" % id(self)
        person = cmds.create_person(date, gender, fn, ln, source)
        self.id = person.get_id()
        self._commit()

class DummyGroup(TestEntity):
    def __init__(self, session, id=None):
        super(DummyGroup, self).__init__(session, id)
        self.get_attr = "get_group"

    def _create_obj(self):
        tr = self._get_tr()
        name = 'unittest_gr%s' % id(self)
        group = tr.get_commands().create_group(name)
        self.id = group.get_id()
        self._commit()

    def __del__(self):
        if not self._keep:
            for gm in self.get_group_members():
                group.remove_member(gm)
            if self._get_obj().is_posix():
                self._get_obj().demote_posix()
            super(DummyGroup, self).__del__()

    def add_member(self, account):
        tr = self._get_tr()
        union_type = tr.get_group_member_operation_type("union")
        self._get_obj().add_member(account._get_obj(), union_type)
        self._commit()

class DummyAccount(TestEntity):
    def __init__(self, session, owner, id=None):
        self.owner = owner
        super(DummyAccount, self).__init__(session)
        self.get_attr = "get_account"

    def __del__(self):
        if not self._keep:
            self._commit() # get a new transaction
            groups = self._get_obj().get_groups()
            for group in groups:
                for i in group.get_group_members():
                    if i.get_member().get_id() == self.id:
                        group.remove_member(i)
            self._commit()
            if self._get_obj().is_posix():
                self._get_obj().demote_posix()
            self._commit()
            super(DummyAccount, self).__del__()

    def _create_obj(self):
        tr = self._get_tr()
        c = tr.get_commands()
        name = 'unittest_ac%s' % id(self)
        date = tr.get_commands().get_date_none()
        account = c.create_account(name, self.owner._get_obj(), date)
        self.id = account.get_id()
        self._commit()

    def promote_posix(self, group):
        tr = self._get_tr()
        c = tr.get_commands()
        shell = tr.get_posix_shell('bash')
        uid = c.get_free_uid()
        self._get_obj().promote_posix(uid, group._get_obj(), shell)
        self._commit()
