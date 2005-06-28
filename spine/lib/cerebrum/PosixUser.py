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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseAttr

from Account import Account
from Group import Group
from Types import CodeType, GroupMemberOperationType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['PosixUser', 'PosixShell']

import Cerebrum.modules.PosixUser

table = 'posix_shell_code'
class PosixShell(CodeType):
    primary = [
        DatabaseAttr('id', table, int),
    ]
    slots = [
        DatabaseAttr('name', table, str),
        DatabaseAttr('shell', table, str)
    ]
    method_slots = []

    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }
registry.register_class(PosixShell)

def get_gecos(self):
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    p.find(self.get_id())

    return p.get_gecos()

table = 'posix_user'
Account.register_attribute(DatabaseAttr('posix_uid', table, int,
                                        write=True, optional=True))
Account.register_attribute(DatabaseAttr('primary_group', table, Group,
                                        write=True, optional=True))
Account.register_attribute(DatabaseAttr('pg_member_op', table,
                                        GroupMemberOperationType,
                                        write=True, optional=True))
Account.register_attribute(DatabaseAttr('gecos', table, str, write=True,
                                        optional=True), get=get_gecos)
Account.register_attribute(DatabaseAttr('shell', table, PosixShell,
                                        write=True, optional=True))
Account.db_attr_aliases[table] = {'id':'account_id', 'primary_group':'gid'}

Account.build_methods()
Account.search_class.build_methods()

def is_posix(self):
    """Check if a account has been promoted to posix.
    """
    account_search = registry.AccountSearcher()
    account_search.set_id(self.get_id())
    account_search.set_posix_uid_exists(True)
    where = 'account_info.account_id = posix_user.account_id'
    result = account_search.search(sql_where=where)
    return result and True or False

Account.register_method(Method('is_posix', bool), is_posix)

def promote_posix(self, primary_group, shell):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    posix_uid = p.get_free_uid()
    p.populate(posix_uid, primary_group.get_id(), None, shell.get_id(), parent=obj)
    p.write_db()

Account.register_method(Method('promote_posix', None, args=[('primary_group', Group), ('shell', PosixShell)], write=True), promote_posix)

# arch-tag: 6397155e-c46c-4e57-a5f7-54d2f046f622
