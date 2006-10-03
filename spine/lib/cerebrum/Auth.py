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
from Types import CodeType

from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['AuthOperationCode', 'AuthOperationSet', 'AuthOperation']

table = 'auth_op_code'
class AuthOperationCode(CodeType):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    )

    db_attr_aliases = {
        table: {
            'id':'code',
            'name':'code_str'
        }
    }
registry.register_class(AuthOperationCode)

table = 'auth_operation_set'
class AuthOperationSet(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str, write=True),
        DatabaseAttr('description', table, str, write=True)
    )

    db_attr_aliases = {
        table: {
            'id':'op_set_id',
        }
    }
    def add_operation(self, operation):
        db = self.get_database()
        obj_id = int(db.nextval('code_seq'))
        AuthOperation._create(db, obj_id, operation, self)
    add_operation.signature = None
    add_operation.signature_name = 'add_operation'
    add_operation.signature_args = [AuthOperationCode]
    add_operation.signature_write = True
    
    def remove_operation(self, operation):
        db = self.get_database()
        ss = registry.AuthOperationSearcher(db)
        ss.set_op_set(self)
        ss.set_op(operation)
        ops = ss.search()
        for op in ops:
            op.delete()
    remove_operation.signature = None
    remove_operation.signature_name = 'remove_operation'
    remove_operation.signature_args = [AuthOperationCode]
    remove_operation.signature_write = True
    
    def delete(self):
        s = registry.AuthOperationSearcher(self.get_database())
        s.set_op_set(self)
        for i in s.search():
            i.delete()
        self._delete_from_db()
        self._delete()
    delete.signature = None
    delete.signature_name = 'delete'
    delete.signature_write = True

registry.register_class(AuthOperationSet)

def create_auth_operation_set(self, name, description):
    db = self.get_database()
    obj_id = int(db.nextval('code_seq'))
    AuthOperationSet._create(db, obj_id, name, description)
    return AuthOperationSet(db, obj_id)
create_auth_operation_set.signature = AuthOperationSet
create_auth_operation_set.signature_args = [str, str]
create_auth_operation_set.signature_write = True


table = 'auth_operation'
class AuthOperation(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('op', table, AuthOperationCode),
        DatabaseAttr('op_set', table, AuthOperationSet),
    )
    db_attr_aliases = {
        table: {
            'id':'op_id',
            'op':'op_code',
            'op_set':'op_set_id',
        }
    }
    def delete(self):
        self._delete_from_db()
        self._delete()
    delete.signature = None
    delete.signature_name = 'delete'
    delete.signature_write = True

registry.register_class(AuthOperation)

def get_operations(self):
    db = self.get_database()
    aos = registry.AuthOperationSearcher(db)
    aos.set_op_set(self)
    return aos.search()
get_operations.signature = [AuthOperation]
get_operations.signature_name = 'get_operations'

Commands.register_methods([create_auth_operation_set])
AuthOperationSet.register_methods([get_operations])
# arch-tag: 3dd57534-233c-4cc1-aa00-b929fd7fb24b
