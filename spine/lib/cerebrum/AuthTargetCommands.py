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

import sets

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method

from Commands import Commands
from Auth import *
from Entity import Entity, EntityType

from SpineLib import Registry
registry = Registry.get_registry()
from server.Authorization import Authorization

__all__ = ['AuthTargetCommands']

table = 'auth_target_commands' # FIXME: better name? auth_target_super?
class AuthTargetCommands(DatabaseClass):
    primary = (
        DatabaseAttr('user', table, Entity),
        DatabaseAttr('op_set', table, AuthOperationSet),
    )
    slots = (
        DatabaseAttr('user_type', table, EntityType),
    )
    db_attr_aliases = {
        table:{
            'user':'user_id',
            'op_set':'op_set_id',
        }
    }
registry.register_class(AuthTargetCommands)

def add_auth_commands(self, user, op_set):
    db = self.get_database()
    AuthTargetCommands._create(db, user, op_set, user.get_type())
m = Method('add_auth_commands', None, args=[('user', Entity), ('op_set', AuthOperationSet)], write=True)
Commands.register_method(m, add_auth_commands)

def del_auth_commands(self, user, op_set):
    obj = AuthTargetCommands(self.get_database(), user)
    obj._delete_from_db()
    obj._delete()
m = Method('del_auth_commands', None, args=[('user', Entity), ('op_set', AuthOperationSet)], write=True)
Commands.register_method(m, del_auth_commands)

class AuthTargetCommandsHandler:
    def __init__(self, auth):
        self.commands = {}

        for user in auth.users:
            op_search = registry.AuthOperationSearcher(auth.db)

            m_search = registry.AuthOperationSetMemberSearcher(auth.db)
            op_search.add_intersection('', m_search, 'op')

            c_search = registry.AuthTargetCommandsSearcher(auth.db)
            c_search.set_user(user)
            m_search.add_intersection('op_set', c_search, 'op_set')
            
            for op in op_search.search():
                op_class = op.get_op_class()
                op_method = op.get_op_method()
                try:
                    self.commands[op_class].add(op_method)
                except KeyError:
                    self.commands[op_class] = sets.Set([op_method])

    def get_permissions(self, obj):
        operations = sets.Set()
        for cls in (obj.__class__, ) + obj.builder_parents:
            op_class = cls.__name__
            for op_method in self.commands.get(op_class, ()):
                operations.add((op_class, op_method))
        return operations

Authorization.handlers.append(AuthTargetCommandsHandler)

# arch-tag: 43f45d5c-9597-11da-9115-bcb0d0e381ab
