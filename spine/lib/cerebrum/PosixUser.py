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
Account.register_attribute(DatabaseAttr('posix_uid', table, int, optional=True))
Account.register_attribute(DatabaseAttr('primary_group', table, Group, optional=True))
Account.register_attribute(DatabaseAttr('pg_member_op', table, GroupMemberOperationType, optional=True))
Account.register_attribute(DatabaseAttr('gecos', table, str, optional=True), get=get_gecos)
Account.register_attribute(DatabaseAttr('shell', table, PosixShell, optional=True))
Account.db_attr_aliases[table] = {'id':'account_id', 'primary_group':'gid'}

Account.build_methods()
Account.search_class.build_methods()

# arch-tag: 6397155e-c46c-4e57-a5f7-54d2f046f622
