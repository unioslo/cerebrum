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

__all__ = ['AuthSuper']

table = 'auth_target_super' # FIXME: better name? auth_target_super?
class AuthTargetSuper(DatabaseClass):
    primary = (
        DatabaseAttr('user', table, Entity),
    )
    slots = (
        DatabaseAttr('type', table, EntityType),
    )
    db_attr_aliases = {
        table: {
            'user':'user_id',
            'type':'user_type'
        }
    }
registry.register_class(AuthTargetSuper)

def add_auth_super_user(self, user):
    db = self.get_database()
    AuthTargetSuper._create(db, user, user.get_type())
m = Method('add_auth_super_user', None, args=[('user', Entity)], write=True)
Commands.register_method(m, add_auth_super_user)

def del_auth_super_user(self, user):
    AuthTargetSuper(self.get_database(), user)._delete_from_db()
m = Method('del_auth_super_user', None, args=[('user', Entity)], write=True)
Commands.register_method(m, del_auth_super_user)

class AuthTargetSuperHandler:
    def __init__(self, auth_session):
        for user in auth_session.users:
            s = registry.AuthTargetSuperSearcher(auth_session.db)
            s.set_user(user)
            if s.search():
                auth_session.superuser = True
                break

Authorization.handlers.append(AuthTargetSuperHandler)

# arch-tag: cab34cfc-9431-11da-853d-0246f7b3b699
