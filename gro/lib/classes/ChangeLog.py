# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import Registry
registry = Registry.get_registry()

__all__ = ['ChangeType', 'ChangeLog']

table = 'change_type'
class ChangeType(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int),
    ]
    slots = [
        DatabaseAttr('category', table, str),
        DatabaseAttr('type', table, str),
        DatabaseAttr('msg', table, str)
    ]

    db_attr_aliases = {
        table: {
            'id':'change_type_id',
            'msg':'msg_string'
        }
    }
registry.register_class(ChangeType)

table = 'change_log'
class ChangeLog(DatabaseClass):
    primary = [
        DatabaseAttr('id', table, int)
    ]
    slots = [
        DatabaseAttr('timestamp', table, Date),
        DatabaseAttr('subject', table, Entity),
        DatabaseAttr('type', table, ChangeType),
        DatabaseAttr('destination', table, str), # Entity
        DatabaseAttr('params', table, str),
        DatabaseAttr('change_by', table, str), # Entity
        DatabaseAttr('change_program', table, str),
        DatabaseAttr('description', table, str),
    ]

    db_attr_aliases = {
        table:{
            'id':'change_id',
            'timestamp':'tstamp',
            'subject':'subject_entity',
            'type':'change_type_id',
            'destination':'dest_entity',
            'params':'change_params'
        }
    }
registry.register_class(ChangeLog)

# arch-tag: 1ca69631-04d1-44b1-b766-1eebd7b072fc
