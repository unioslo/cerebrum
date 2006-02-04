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

__all__ = ['AuthTargetEntityHandler']

table = 'auth_target_entity'
class AuthTargetEntity(DatabaseClass):
    primary = (
        DatabaseAttr('user', table, Entity),
        DatabaseAttr('op_set', table, AuthOperationSet),
        DatabaseAttr('entity', table, Entity)
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
registry.register_class(AuthTargetEntity)

def add_auth_target_entity(self, user, op_set, entity):
    db = self.get_database()
    AuthTargetEntity._create(db, user, op_set, entity, user.get_type())
m = Method('add_auth_target_entity', None, args=[('user', Entity), ('op_set', AuthOperationSet), ('entity', Entity)], write=True)
Commands.register_method(m, add_auth_target_entity)

def del_auth_target_entity(self, user, op_set, entity):
    AuthTargetEntity(self.get_database(), user, op_set, entity)._delete_from_db()
m = Method('del_auth_target_entity', None, args=[('user', Entity), ('op_set', AuthOperationSet), ('entity', Entity)], write=True)
Commands.register_method(m, del_auth_target_entity)

class AuthTargetEntityHandler:
    def __init__(self, auth):
        self.auth = auth

    def get_permissions(self, obj, method):
        operations = sets.Set()
        if isinstance(obj, Entity):
            for user in self.auth.users:
                op_search = registry.AuthOperationSearcher(self.auth.db)

                m_search = registry.AuthOperationSetMemberSearcher(self.auth.db)
                op_search.add_intersection('', m_search, 'op')

                s = registry.AuthTargetEntitySearcher(self.auth.db)
                s.set_user(user)
                s.set_entity(obj)
                m_search.add_intersection('op_set', s, 'op_set')

                for op in op_search.search():
                    operations.add((op.get_op_class(), op.get_op_method()))

        return operations

Authorization.handlers.append(AuthTargetEntityHandler)

# arch-tag: 445b82d4-9597-11da-91ce-85785560b498
