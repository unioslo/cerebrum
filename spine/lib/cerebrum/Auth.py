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

from Entity import Entity
from Types import AuthOperationType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['AuthOperationSet', 'AuthOperation', 'AuthOperationAttr', 'AuthRole']

# samling med operasjoner
table = 'auth_operation_set'
class AuthOperationSet(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int)
    ]
    slots = [
        DatabaseAttr('name', table, str)
    ]
    method_slots = [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = {
        table: {
            'id':'op_set_id'
        }
    }

    def delete(self):
        self._delete()
        self.invalidate()

registry.register_class(AuthOperationSet)

# AuthOperationSet innholder disse
table = 'auth_operation'
class AuthOperation(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int)
    ]
    slots = [
        DatabaseAttr('operation_type', table, AuthOperationType),
        DatabaseAttr('operation_set', table, AuthOperationSet)
    ]
    method_slots = [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = {
        table: {
            'id':'op_id',
            'operation_type':'op_code',
            'operation_set':'op_set_id'
        }
    }

    def delete(self):
        self._delete()
        self.invalidate()

registry.register_class(AuthOperation)

# ektra argumenter for operasjoner
table = 'auth_op_attrs'
class AuthOperationAttr(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int)
    ]
    slots = [
        DatabaseAttr('attr', table, str)
    ]
    method_slots = [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = {
        table: {
            'id':'op_id'
        }
    }

    def delete(self):
        self._delete()
        self.invalidate()

registry.register_class(AuthOperationAttr)

table = 'auth_role'
class AuthRole(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('operation_set', table, AuthOperationSet),
        DatabaseAttr('target', table, Entity)
    ]
    method_slots = [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = {
        table: {
            'entity':'entity_id',
            'operation_set':'op_set_id',
            'target':'op_target_id'
        }
    }

    def delete(self):
        self._delete()
        self.invalidate()

registry.register_class(AuthRole)

# Methods for creating the diffrent auth-classes.
auth_seq = 'code_seq'

def create_auth_operation_set(self, id, name):
    db = self.get_database()
    obj_id = int(db.nextval(auth_seq))
    AuthOperationSet._create(db, obj_id, id=id, name=name)
    return AuthOperationSet(obj_id, write_lock=self.get_writelock_holder())

m = Method('create_auth_operation_set', AuthOperationSet,
           args=[('id', int), ('name', str)], write=True)
Commands.register_method(m, create_auth_operation_set)

def create_auth_operation(self, id, operation_type, operation_set):
    db = self.get_database()
    obj_id = int(db.nextval(auth_seq))
    AuthOperation._create(db, obj_id, operation_type, operation_set)
    return AuthOperation(obj_id, write_lock=self.get_writelock_holder())

m = Method('create_auth_operation', AuthOperation, write=True,
           args=[('id', int), ('operation_type', AuthOperationType),
                 ('operation_set', AuthOperationSet)])
Commands.register_method(m, create_auth_operation)

def create_auth_operation_attr(self, id, attr):
    db = self.get_database()
    obj_id = int(db.nextval(auth_seq))
    AuthOperationAttr._create(db, obj_id, id=id, attr=attr)
    return AuthOperationAttr(obj_id, write_lock=self.get_writelock_holder())

m = Method('create_auth_operation_attr', AuthOperationAttr,
           args=[('id', int), ('attr', str)], write=True)
Commands.register_method(m, create_auth_operation_attr)

def create_auth_role(self, entity, operation_set, target):
    db = self.get_database()
    obj_id = int(db.nextval(auth_seq))
    AuthRole._create(db, obj_id, entity, operation_set, target)
    return AuthRole(obj_id, write_lock=self.get_writelock_holder())

m = Method('create_auth_role', AuthRole, write=True,
           args=[('entity', Entity), ('operation_set', AuthOperationSet),
                 ('target', Entity)])
Commands.register_method(m, create_auth_role)

# arch-tag: 3dd57534-233c-4cc1-aa00-b929fd7fb24b
