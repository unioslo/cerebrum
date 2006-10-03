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

def debug(func):
    fname = func.__module__, func.func_name
    def decorator(*args, **kwargs):
        print fname, args
        return func(*args, **kwargs)
    return decorator
    

class TestEntity(object):
    def __init__(self, _session, _id=None):
        self._keep = False
        self._session = _session
        self._open = False
        self._get_attr = "get_entity"
        if _id:
            self._id = _id
        else:
            self._id = self._create_obj()

    def __del__(self):
        if not hasattr(self, '_session') or not hasattr(self, '_id'):
            return # Object not initialized properly.
        if not self._keep:
            obj = self._get_obj()
            obj.delete()
            self._commit()
        
    def _get_tr(self):
        if not self._open:
            self.tr = self._session.new_transaction()
            self._open = True
        return self.tr

    def _get_obj(self, tr=None):
        tr = tr or self._get_tr()
        attr = getattr(tr, self._get_attr)
        return attr(self._id)

    def _commit(self, tr=None):
        if tr:
            assert tr is self.tr
        if self._open:
            self._open = False
            self.tr.commit()

    def __getattr__(self, attr):
        """ Decorate the method calls so we can make sure all changes are commited. """
        if attr.startswith("_"):
            super(TestEntity, self).__getattribute__(attr)
        obj = self._get_obj()
        f = getattr(obj, attr)
        def w(*args, **kwargs):
            r = f(*args, **kwargs)
            self._commit()
            return r
        return w

    def keep(self):
        self._keep = True

class DummyPerson(TestEntity):
    def __init__(self, _session, _id=None):
        super(DummyPerson, self).__init__(_session, _id)
        self._get_attr = "get_person"

    def _create_obj(self):
        tr = self._get_tr()
        cmds = tr.get_commands()
        date = cmds.get_date_now()
        gender = tr.get_gender_type('M')
        source = tr.get_source_system('Manual')
        fn = "unit_%s" % id(self)
        ln = "test_%s" % id(self)
        person = cmds.create_person(date, gender, fn, ln, source)
        _id = person.get_id()
        self._commit()
        return _id

class DummyGroup(TestEntity):
    def __init__(self, _session, _id=None):
        super(DummyGroup, self).__init__(_session, _id)
        self._get_attr = "get_group"

    def _create_obj(self):
        tr = self._get_tr()
        name = 'tgr%s' % str(id(self))[1:6]
        group = tr.get_commands().create_group(name)
        _id = group.get_id()
        self._commit()
        return _id

    def __del__(self):
        if not hasattr(self, '_session'):
            return
        if not self._keep and self._id:
            group = self._get_obj()
            for gm in group.get_group_members():
                member = gm.get_member()
                if member.is_posix():
                    if group.get_id() == member.get_primary_group().get_id():
                        member.demote_posix()
                group.remove_member(gm)
            if group.is_posix():
                group.demote_posix()
            super(DummyGroup, self).__del__()

    def add_member(self, aid):
        tr = self._get_tr()
        union_type = tr.get_group_member_operation_type("union")
        account = tr.get_account(aid)
        self._get_obj().add_member(account, union_type)
        self._commit()

class DummyAccount(TestEntity):
    def __init__(self, _session, owner, _id=None):
        self.owner = owner
        super(DummyAccount, self).__init__(_session)
        self._get_attr = "get_account"

    def __del__(self):
        if not hasattr(self, '_session'):
            return
        if not self._keep and self._id:
            obj = self._get_obj()
            if obj.is_posix():
                obj.demote_posix()
            self._commit() # get a new transaction
            groups = self._get_obj().get_groups()
            for group in groups:
                for i in group.get_group_members():
                    if i.get_member().get_id() == self._id:
                        group.remove_member(i)
            self._commit()
            super(DummyAccount, self).__del__()

    def _create_obj(self):
        tr = self._get_tr()
        c = tr.get_commands()
        name = 'tac%s' % str(id(self))[1:6]
        date = tr.get_commands().get_date_none()
        account = c.create_account(name, self.owner._get_obj(), date)
        _id = account.get_id()
        self._commit()
        return _id

    def promote_posix(self, gid):
        tr = self._get_tr()
        uid = tr.get_commands().get_free_uid()
        group = tr.get_group(gid)
        shell = tr.get_posix_shell('bash')
        self._get_obj().promote_posix(uid, group, shell)
        self._commit(tr)
