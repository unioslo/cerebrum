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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Date import Date

from Entity import Entity
from Types import QuarantineType

from SpineLib import Registry
from SpineLib.SpineExceptions import NotFoundError, TooManyMatchesError, AlreadyExistsError
registry = Registry.get_registry()

__all__ = ['EntityQuarantine']

table = 'entity_quarantine'

class EntityQuarantine(DatabaseClass):
    primary = (
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('type', table, QuarantineType),
    )
    slots = (
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('description', table, str, write=True),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('start_date', table, Date, write=True),
        DatabaseAttr('end_date', table, Date, write=True, optional=True),
        DatabaseAttr('disable_until', table, Date, write=True, optional=True)
    )


    db_attr_aliases = {
        table:{
            'entity':'entity_id',
            'type':'quarantine_type',
            'creator':'creator_id'
        }
    }

    def get_auth_entity(self):
        return self.get_entity()
    get_auth_entity.signature = Entity

    def is_active(self):
        now = mx.DateTime.now()

        start = self.get_start_date()
        end = self.get_end_date()
        disable = self.get_disable_until()

        return (start <= now
            and (end is None or end >= now)
            and (disable is None or disable < now))
    is_active.signature = bool
    is_active.signature_name = 'is_active'

registry.register_class(EntityQuarantine)

def get_quarantine(self, type):
    s = registry.EntityQuarantineSearcher(self.get_database())
    s.set_type(type)
    s.set_entity(self)
    result = s.search()
    if not result:
        raise NotFoundError('Entity has no quarantine of the given type.')
    elif len(result) > 1:
        raise TooManyMatchesError('Entity has more than one quarantine of the given type.')
    return result[0]
get_quarantine.signature = EntityQuarantine
get_quarantine.signature_args = [QuarantineType]
get_quarantine.signature_exceptions = [NotFoundError, TooManyMatchesError]

def get_quarantines(self):
    s = registry.EntityQuarantineSearcher(self.get_database())
    s.set_entity(self)
    return s.search()
get_quarantines.signature = [EntityQuarantine]

def get_all_quarantines(self):
    q = self.get_quarantines()
    if self.get_type().get_name() == 'account':
        q += self.get_owner().get_all_quarantines()
    return q
get_all_quarantines.signature = [EntityQuarantine]

def get_active_quarantines(self):
    return [i for i in self.get_quarantines() if i.is_active()]
get_active_quarantines.signature = [EntityQuarantine]

def is_quarantined(self):
    import Cerebrum.QuarantineHandler

    quarantines = [i.get_type() for i in self.get_quarantines() if i.is_active()]
    qh = Cerebrum.QuarantineHandler.QuarantineHandler(self.get_database(), quarantines)

    return qh.should_skip() or qh.is_locked()
is_quarantined.signature = bool

def add_quarantine(self, type, description, start, end, disable_until):
    """Add a quarantine to the entity.

    If start date is false the current time is set as start-date.
    """

    db = self.get_database()
    obj = self._get_cerebrum_obj()

    if obj.get_entity_quarantine(type.get_id()):
        raise AlreadyExistsError("A quarantine of the type %s already exists, and there can only be one." % type.get_name())

    if start:
        start = start._value
    else:
        start = mx.DateTime.now()

    if end:
        end = end._value
    if disable_until:
        disable_until = disable_until._value

    obj.add_entity_quarantine(type.get_id(), db.change_by, description, start, end)
    if disable_until:
        obj.disable_entity_quarantine(type.get_id(), disable_until)
add_quarantine.signature = None
add_quarantine.signature_args=[QuarantineType, str, Date, Date, Date]
add_quarantine.signature_exceptions=[AlreadyExistsError]
add_quarantine.signature_write=True
add_quarantine.signature_auth_attr = 0

def remove_quarantine(self, type):
    db = self.get_database()
    obj = self._get_cerebrum_obj()
    obj.delete_entity_quarantine(type.get_id())
remove_quarantine.signature = None
remove_quarantine.signature_args=[QuarantineType]
remove_quarantine.signature_write=True
add_quarantine.signature_auth_attr = 0

Entity.register_methods([get_quarantine, get_quarantines, get_all_quarantines, get_active_quarantines, is_quarantined, add_quarantine, remove_quarantine])


# arch-tag: 07667d91-f0b5-4152-8e83-36994ffa9b8e
