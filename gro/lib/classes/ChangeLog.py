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

import Database

from GroBuilder import GroBuilder
from Builder import Attribute, Method
from Searchable import Searchable

import Registry
registry = Registry.get_registry()

__all__ = ['ChangeType', 'ChangeEvent']

# sukk. hvorfor er ikke denne implementert som konstanter?
class ChangeType(GroBuilder):
    primary = [Attribute('category', 'string'), Attribute('type', 'string')]
    slots = primary + [Attribute('id', 'long'), Attribute('msg', 'string')]

    def get_by_id(cls, id):
        db = Database.get_database()
        row = db.query_1('''SELECT category, type, msg_string
                            FROM [:table schema=cerebrum name=change_type]
                            WHERE change_type_id = %s''' % id)
        return ChangeType(id=id, category=row['category'], type=row['type'], msg=['msg_string'])

    get_by_id = classmethod(get_by_id)



class ChangeEvent(GroBuilder, Searchable):
    primary = [Attribute('id', 'long')]
    slots = primary + [Attribute('timestamp', 'Date'), Attribute('subject', 'Entity'),
                       Attribute('change_type', 'ChangeType'), Attribute('destination', 'Entity'),
                       Attribute('params', 'string'), Attribute('change_by', 'Entity'),
                       Attribute('change_program', 'string')]

    def get_by_row(cls, row):
        c = cls(int(row['change_id']))
        c._timestamp = row['tstamp']
        c._subject = registry.Entity(int(row['subject_entity']))
        c._change_type = ChangeType.get_by_id(int(row['change_type_id']))
        destination = row['dest_entity']
        c._destination = destination and registry.Entity(int(destination)) or None
        c._params = row['change_params']
        c._change_by = row['change_by']
        c._change_program = row['change_program']
        return c

    get_by_row = classmethod(get_by_row)

    def _load_change_event(self):
        db = self.get_database()
        row = db.query_1('''SELECT change_id, tstamp, subject_entity, change_type_id,
                           dest_entity, change_params, change_by, change_program
                    FROM [:table schema=cerebrum name=change_log]
                    WHERE change_id = %s''' % self._id)
        self.get_by_row(row)

    load_id = load_timestamp = load_params = load_change_by = load_change_program = _load_change_event

    def create_search_method(cls):
        def search(self, id=None, timestamp=None, subject=None, change_type=None, destination=None, change_by=None):
            if id is None:
                id = 0
            if change_type is not None:
                change_type = [change_type.get_id()]

            if subject is not None:
                subject = subject.get_entity_id()

            if destination is not None:
                destination = destination.get_entity_id()
                
            db = self.get_database()
            events = []
            for row in db.get_log_events(start_id=id, types=change_type, subject_entity=subject,
                                     dest_entity=destination):
                events.append(cls.get_by_row(row))
            return events
        return search

    create_search_method = classmethod(create_search_method)

# arch-tag: 1ca69631-04d1-44b1-b766-1eebd7b072fc
