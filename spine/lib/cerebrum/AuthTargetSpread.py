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
from Types import Spread

from SpineLib import Registry
registry = Registry.get_registry()
from server.Authorization import Authorization

__all__ = ['AuthTargetSpread']

table = 'auth_target_spread'
class AuthTargetSpread(DatabaseClass):
    primary = (
        DatabaseAttr('user', table, Entity),
        DatabaseAttr('op_set', table, AuthOperationSet),
        DatabaseAttr('spread', table, Spread)
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
registry.register_class(AuthTargetSpread)

def add_auth_target_spread(self, user, op_set, spread):
    db = self.get_database()
    AuthTargetSpread._create(db, user, op_set, spread, user.get_type())
m = Method('add_auth_target_spread', None, args=[('user', Entity), ('op_set', AuthOperationSet), ('spread', Spread)], write=True)
Commands.register_method(m, add_auth_target_spread)

def del_auth_target_spread(self, user, op_set, spread):
    obj = AuthTargetSpread(self.get_database(), user, op_set, spread)
    obj._delete_from_db()
    obj._delete()
m = Method('del_auth_target_spread', None, args=[('user', Entity), ('op_set', AuthOperationSet), ('spread', Spread)], write=True)
Commands.register_method(m, del_auth_target_spread)

class AuthTargetSpreadHandler:
    def __init__(self, auth):
        self.commands = {}

        for user in auth.users:
            op_search = registry.AuthOperationSearcher(auth.db)

            m_search = registry.AuthOperationSetMemberSearcher(auth.db)
            op_search.add_intersection('', m_search, 'op')

            c_search = registry.AuthTargetSpreadSearcher(auth.db)
            m_search.add_intersection('op_set', c_search, 'op_set')

            for spread in registry.SpreadSearcher(auth.db).search():
                c_search.set_spread(spread)
                for op in op_search.search():
                    operation = op.get_op_class(), op.get_op_method()
                    try:
                        self.commands[spread].add(operation)
                    except KeyError:
                        self.commands[spread] = sets.Set([operation])


    def get_permissions(self, obj):
        if isinstance(obj, Entity):
            operations = sets.Set()
            for spread in obj.get_spreads():
                operations.update(self.commands(spread))
            return operations
        elif hasattr(obj, 'get_primary_key'): # is not a command class
            operations = None
            for i in obj.get_primary_key():
                if isinstance(i, Entity):
                    if operations is None:
                        operations = sets.Set(self.get_permissions(i))
                    else:
                        operations.intersection_update(self.get_permissions(i))
            return operations or ()
        # FIXME: fetch all permissions if obj is a search object
        return ()

Authorization.handlers.append(AuthTargetSpreadHandler)

# arch-tag: 445b82d4-9597-11da-91ce-85785560b498
