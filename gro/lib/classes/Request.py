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

from DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Date import Date
from Types import CodeType

import Registry
registry = Registry.get_registry()

__all__ = ['RequestCode', 'Request']

table = 'bofhd_request_code'
class RequestCode(CodeType):
    primary = [
        DatabaseAttr('id', table, int),
    ]
    slots = [
        DatabaseAttr('name', table, str),
        DatabaseAttr('description', table, str)
    ]

    db_attr_aliases = {
        table: {
            'id':'code',
            'name':'code_str'
        }
    }
registry.register_class(RequestCode)

table = 'bofhd_request'
class Request(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int)
    ]
    slots = [
        DatabaseAttr('requester', table, Entity),
        DatabaseAttr('run_at', table, Date),
        DatabaseAttr('operation', table, RequestCode),
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('destination', table, str), # Entity
        DatabaseAttr('state_data', table, str),
    ]

    db_attr_aliases = {
        table:{
            'id':'request_id',
            'requester':'requestee_id',
            'entity':'entity_id',
            'destination':'destination_id',
        }
    }
registry.register_class(Request)

# arch-tag: 7c4104c6-0b16-4b78-88f7-565d5608bf93
