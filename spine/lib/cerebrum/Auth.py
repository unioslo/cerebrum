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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method

from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['AuthOperation', 'AuthOperationSet', 'AuthOperationSetMember']

table = 'auth_operation'
class AuthOperation(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('op_class', table, str),
        DatabaseAttr('op_method', table, str)
    )
registry.register_class(AuthOperation)

table = 'auth_operation_set'
class AuthOperationSet(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    )
    method_slots = (
        Method('add_operation', None, args=[('operation', AuthOperation)], write=True),
        Method('get_operations', [AuthOperation]),
        Method('delete', None)
    )

    def add_operation(self, operation):
        AuthOperationSetMember._create(self.get_database(), operation, self)

    def get_operations(self):
        db = self.get_database()
        s = registry.AuthOperationSearcher(db)
        ss = registry.AuthOperationSetMemberSearcher(db)
        ss.set_op_set(self)
        s.add_join('', ss, 'op')
        return s.search()

    def delete(self):
        s = registry.AuthOperationSetMemberSearcher(self.get_database())
        s.set_op_set(self)
        for i in s.search():
            i.delete()
        self._delete_from_db()
        self._delete()
registry.register_class(AuthOperationSet)

table = 'auth_operation_set_member'
class AuthOperationSetMember(DatabaseClass):
    primary = (
        DatabaseAttr('op', table, AuthOperation),
        DatabaseAttr('op_set', table, AuthOperationSet)
    )
    method_slots = (
        Method('delete', None),
    )
    db_attr_aliases = {
        table: {
            'op':'op_id',
            'op_set':'op_set_id'
        }
    }
    def delete(self):
        self._delete_from_db()
        self._delete()
registry.register_class(AuthOperationSetMember)

def create_auth_operation(self, op_class, op_method):
    db = self.get_database()
    obj_id = int(db.nextval('auth_seq'))
    AuthOperation._create(db, obj_id, op_class, op_method)
    return AuthOperation(db, obj_id)
m = Method('create_auth_operation', AuthOperation,
           args=[('op_class', str), ('op_method', str)], write=True)
Commands.register_method(m, create_auth_operation)

def create_auth_operation_set(self, name, description):
    db = self.get_database()
    obj_id = int(db.nextval('auth_seq'))
    AuthOperationSet._create(db, obj_id, name, description)
    return AuthOperationSet(db, obj_id)
m = Method('create_auth_operation_set', AuthOperationSet,
           args=[('name', str), ('description', str)], write=True)
Commands.register_method(m, create_auth_operation_set)

# arch-tag: 3dd57534-233c-4cc1-aa00-b929fd7fb24b
