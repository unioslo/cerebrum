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

import mx.DateTime

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Entity import Entity
from Date import Date
from Types import QuarantineType

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['EntityQuarantine']

table = 'entity_quarantine'

class EntityQuarantine(DatabaseClass):
    primary = [
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('type', table, QuarantineType),
    ]
    slots = [
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('description', table, str, write=True),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('start_date', table, Date, write=True),
        DatabaseAttr('end_date', table, Date, write=True),
        DatabaseAttr('disable_until', table, Date, write=True)
    ]

    method_slots = [
        Method('is_active', bool)
    ]

    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'type':'quarantine_type',
            'creator':'creator_id'
        }
    }

    def is_active():
        now = mx.DateTime.now()

        start = self.get_starte_date()
        end = self.get_end_date()
        disable = self.get_disable_until()

        return (start <= now
            and (end is None or end >= now)
            and (disable is None or disable < now))

registry.register_class(EntityQuarantine)

def get_quarantines(self):
    s = registry.EntityQuarantineSearcher(self)
    s.set_entity(self)
    return s.search()

Entity.register_method(Method('get_quarantines', [EntityQuarantine]), get_quarantines)

def get_all_quarantines(self):
    q = self.get_quarantines()
    if self.get_type().get_name() == 'account':
        q += self.get_owner().get_all_quarantines()
    return q

Entity.register_method(Method('get_all_quarantines', [EntityQuarantine]), get_all_quarantines)

def get_active_quarantines(self):
    return [i for i in self.get_quarantines() if i.is_active()]

def is_quarantined(self):
    import Cerebrum.QuarantineHandler

    quarantines = [i.get_type() for i in self.get_quarantines() if i.is_active()]
    qh = Cerebrum.QuarantineHandler.QuarantineHandler(self.get_database(), quarantines)

    return qh.should_skip() or qh.is_locked()

Entity.register_method(Method('is_quarantined', bool), is_quarantined)

def add_quarantine(self, type, description, start, end, disable_until):
    import mx.DateTime
    db = self.get_database()
    obj = self._get_cerebrum_obj()

    if start:
        start = mx.DateTime.now()
    if end:
        end = end._value
    if disable_until:
        disable_until = disable_until._value

    obj.add_entity_quarantine(type.get_id(), db.change_by, description, start, end)
    if disable_until:
        obj.disable_entity_quarantine(type.get_id(), disable_until)

Entity.register_method(Method('add_quarantine', None, args=[('type', QuarantineType), ('description', str), ('start', Date), ('end', Date), ('disable_until', Date)], write=True), add_quarantine)

# arch-tag: 07667d91-f0b5-4152-8e83-36994ffa9b8e
