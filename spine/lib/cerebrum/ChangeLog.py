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
from SpineLib.Builder import Attribute
from SpineLib.Date import Date

from Entity import Entity
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

from Cerebrum.Utils import Factory
logger = Factory.get_logger()

__all__ = ['ChangeType', 'ChangeLog']

table = 'change_type'
class ChangeType(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('category', table, str),
        DatabaseAttr('type', table, str),
        DatabaseAttr('message', table, str)
    )
    db_attr_aliases = {
        table: {
            'id':'change_type_id',
            'message':'msg_string'
        }
    }
registry.register_class(ChangeType)

table = 'change_log'
class ChangeLog(DatabaseClass):
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('timestamp', table, Date),
        DatabaseAttr('subject_entity', table, int),
        DatabaseAttr('type', table, ChangeType),
        DatabaseAttr('dest_entity', table, int),
        DatabaseAttr('params', table, str),
        DatabaseAttr('change_by', table, Entity),
        DatabaseAttr('change_program', table, str),
        Attribute('message', str),
    )
    db_attr_aliases = {
        table:{
            'id':'change_id',
            'timestamp':'tstamp',
            'type':'change_type_id',
            'params':'change_params'
        }
    }

    def load_message(self):
        args = {
            'subject':self.get_subject_entity(),
            'dest':self.get_dest_entity()
        }
        params = self.get_params()
        if params:
            args.update(cPickle.loads(params))

        msg = self.get_type().get_message() 
        try:
            msg = msg % args
        except KeyError, e:
            logger.debug("Could not %%-ify msg %s with args %s error: %s" % (
                msg, args, e))
            pass    
        if type(msg) is unicode:
            msg = repr(msg)
        self._message = msg
registry.register_class(ChangeLog)

def get_last_changelog_id(self):
    db = self.get_database()
    # db_query_1 will return None when there's no change_log
    #return int(db.query_1('SELECT max(change_id) FROM change_log') or 0)
    # It's much faster, don't ask.
    return int(db.query_1('SELECT change_id FROM change_log ORDER BY change_id DESC LIMIT 1') or 0)

get_last_changelog_id.signature = int
Commands.register_methods([get_last_changelog_id])

def get_history(self):
    s = registry.ChangeLogSearcher(self.get_database())
    s.order_by_desc(s, 'timestamp')
    s.set_subject_entity(self.get_id())
    return s.search()

get_history.signature = [ChangeLog]
Entity.register_methods([get_history])

# arch-tag: 7e73d1d8-0ac3-46a6-a360-1b3efe6e4549
