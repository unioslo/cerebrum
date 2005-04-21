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

import cPickle

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Builder import Method, Attribute

from Entity import Entity
from Date import Date
from Commands import Commands

from SpineLib import Registry
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
        DatabaseAttr('message', table, str)
    ]

    db_attr_aliases = {
        table: {
            'id':'change_type_id',
            'message':'msg_string'
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
        DatabaseAttr('subject', table, Entity, optional=True),
        DatabaseAttr('subject_entity', table, int),
        DatabaseAttr('type', table, ChangeType),
        DatabaseAttr('destination', table, Entity, optional=True),
        DatabaseAttr('params', table, str),
        DatabaseAttr('change_by', table, Entity),
        DatabaseAttr('change_program', table, str),
        DatabaseAttr('description', table, str),
        Attribute('message', str),
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

    def load_message(self):
        args = {'subject':self.get_subject_entity()}

        dest = self.get_destination()
        if dest:
            args['dest'] = dest.get_id()
        params = self.get_params()
        if params:
            args.update(cPickle.loads(params))

        msg = self.get_type().get_message() % args
        if type(msg) is unicode:
            msg = repr(msg)
        self._message = msg
registry.register_class(ChangeLog)

def get_last_changelog_id(self):
    db = self.get_database()
    # db_query_1 will return None when there's no change_log 
    return int(db.query_1('SELECT max(change_id) FROM change_log') or 0)

Commands.register_method(Method('get_last_changelog_id', int), get_last_changelog_id)

def get_history(self):
    s = registry.ChangeLogSearcher()
    s.set_subject(self)
    result = s.search()
    result.sort(lambda a, b: cmp(a.get_id(), b.get_id()))
    return result

Entity.register_method(Method('get_history', [ChangeLog]), get_history)

# arch-tag: 7e73d1d8-0ac3-46a6-a360-1b3efe6e4549
