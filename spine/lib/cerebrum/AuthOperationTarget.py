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

from Commands import Commands
from Auth import *
from Entity import Entity, EntityType

from SpineLib import Registry
registry = Registry.get_registry()
from server.Authorization import Authorization

__all__ = ['AuthOperationTarget']

table = 'auth_op_target' 
class AuthOperationTarget(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('entity_id', table, int),
        DatabaseAttr('target_type', table, str),
        DatabaseAttr('attr', table, str),
    )
    db_attr_aliases = {
        table: {
            'op_target_id':'id',
        }
    }
registry.register_class(AuthOperationTarget)

def add_auth_super_user(self, user):
    db = self.get_database()
    AuthOperationTarget._create(db, user, user.get_type())
add_auth_super_user.signature = None
add_auth_super_user.signature_args = [Entity]
add_auth_super_user.signature_write = True


def del_auth_super_user(self, user):
    AuthOperationTarget(self.get_database(), user)._delete_from_db()
del_auth_super_user.signature = None
del_auth_super_user.signature_args = [Entity]
del_auth_super_user.signature_write = True

Commands.register_method([add_auth_super_user, del_auth_super_user])

class AuthOperationTargetHandler:
    def __init__(self, auth_session):
        for user in auth_session.users:
            s = registry.AuthOperationTargetSearcher(auth_session.db)
            s.set_user(user)
            if s.search():
                auth_session.superuser = True
                break

Authorization.handlers.append(AuthOperationTargetSearcher)

# arch-tag: cab34cfc-9431-11da-853d-0246f7b3b699
