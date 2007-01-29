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

import Cerebrum.Errors
import Cerebrum.modules.PosixUser
from CerebrumClass import CerebrumDbAttr
from Cerebrum.Utils import Factory

from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError

from Account import Account
from Group import Group
from Commands import Commands
from Types import CodeType, GroupMemberOperationType

Commands.register_extention("posixuser")
from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['PosixUser', 'PosixShell']

table = 'posix_shell_code'
class PosixShell(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('shell', table, str)
    )

    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }

registry.register_class(PosixShell)

def get_gecos(self):
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    try:
        p.find(self.get_id())
    except Cerebrum.Errors.NotFoundError:
        raise NotFoundError('Could not find gecos for %s' % self)

    return p.get_gecos()
get_gecos.signature = str
Account.register_methods([get_gecos])

table = 'posix_user'
attrs = [
    CerebrumDbAttr('gecos', table, str, write=True, optional=True),
    CerebrumDbAttr('posix_uid', table, int, write=True, optional=True),
    CerebrumDbAttr('primary_group', table, Group, write=True, optional=True),
    CerebrumDbAttr('pg_member_op', table, GroupMemberOperationType, write=True, optional=True),
    CerebrumDbAttr('shell', table, PosixShell, write=True, optional=True)
]

cerebrumclass = Factory.get('PosixUser')
for attr in attrs:
    attr.cerebrumclass = cerebrumclass
    Account.register_attribute(attr)

Account.db_attr_aliases[table] = {'id':'account_id', 'primary_group':'gid'}
Account.build_methods()
Account.build_search_class()
registry.register_class(Account)

def is_posix(self):
    """Check if a account has been promoted to posix.
    """
    try:
        return self.get_posix_uid() is not None
    except NotFoundError, e:
        return False
    return True

is_posix.signature = bool

def get_free_uid(self):
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    return p.get_free_uid()

get_free_uid.signature = int

def promote_posix(self, posix_uid, primary_group, shell):
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    p.populate(posix_uid, primary_group.get_id(), None, shell.get_id(), parent=obj)
    p.write_db()

promote_posix.signature = None
promote_posix.signature_args = [int, Group, PosixShell]
promote_posix.signature_write = True

def demote_posix(self):
    """Demotes the PosixUser to a normal Account."""
    obj = self._get_cerebrum_obj()
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    p.find(obj.entity_id)
    p.delete_posixuser()

demote_posix.signature = None
demote_posix.signature_write = True

Commands.register_methods([get_free_uid])
Account.register_methods([is_posix, promote_posix, demote_posix])

# arch-tag: 6397155e-c46c-4e57-a5f7-54d2f046f622
