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

from Entity import Entity
from Types import AuthOperationType

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

    db_attr_aliases = {
        table: {
            'id':'op_set_id'
        }
    }
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

    db_attr_aliases = {
        table: {
            'id':'op_id',
            'operation_type':'op_code',
            'operation_set':'op_set_id'
        }
    }
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

    db_attr_aliases = {
        table: {
            'id':'op_id'
        }
    }
registry.register_class(AuthOperationAttr)

table = 'auth_role'
class AuthRole(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('operation_set', table, AuthOperationSet),
        DatabaseAttr('target', table, Entity)
    ]

    db_attr_aliases = {
        table: {
            'entity':'entity_id',
            'operation_set':'op_set_id',
            'target':'op_target_id'
        }
    }
registry.register_class(AuthRole)

