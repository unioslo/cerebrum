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

import time

import Cerebrum.Entity
import Cerebrum.QuarantineHandler
import Cerebrum.modules.Note

from Cerebrum.extlib import sets

from GroBuilder import GroBuilder
from Builder import Attribute, Method
from CerebrumClass import CerebrumClass, CerebrumAttr

from Types import EntityType, Spread
from ContactInfo import ContactInfo
from Address import Address
from EntityAuth import EntityAuth

import Registry
registry = Registry.get_registry()


__all__ = ['Entity']

class Entity(CerebrumClass, EntityAuth):
    primary = [
        CerebrumAttr('id', int, 'entity_id')
    ]
    slots = primary + [
        CerebrumAttr('type', EntityType, 'entity_type')
    ]
    method_slots = CerebrumClass.method_slots + [
        Method('get_spreads', Spread, sequence=True),
    ]

    cerebrum_class = Cerebrum.Entity.Entity
    def __new__(cls, *args, **vargs):
        obj = GroBuilder.__new__(Entity, *args, **vargs)

        if obj.__class__ is Entity: # this is a fresh object
            obj.__init__(*args, **vargs)

        entity_type = obj.get_type()
        entity_class = entity_type.get_class()

        if cls is not entity_class and cls is not Entity:
            raise Exception('wrong class. Asked for %s, but found %s' % (cls, entity_class))
        else:
            obj.__class__ = entity_class

        return obj

    def get_spreads(self):
        e = Cerebrum.Entity.Entity(self.get_database())
        e.entity_id = self.get_id()
        
        spreads = []
        for i in e.get_spread():
            spreads.append(Spread(id=int(i[0])))
            
        return spreads

    def get_addresses(self):
        addresses = []
        e = Cerebrum.Entity.EntityAddress(self.get_database())
        e.entity_id = self.get_id()

        for row in e.get_entity_address():
            addresses.append(Address.getByRow(row))

        return addresses

    def get_contact_info(self):
        contact_info = []

        e = Cerebrum.Entity.EntityContactInfo(self.get_database())
        e.entity_id = self.get_id()

        for row in e.get_contact_info():
            contact_info.append(ContactInfo.getByRow(row))

        return contact_info

    def is_quarantined(self):
        account = Cerebrum.Entity.EntityQuarantine(self.get_database())
        account.entity_id = self.get_id()

        # koka fra bofhd
        quarantines = []      # TBD: Should the quarantine-check have a utility-API function?
        now = self.get_database().DateFromTicks(time.time())
        for qrow in account.get_entity_quarantine():
            if (qrow['start_date'] <= now
                and (qrow['end_date'] is None or qrow['end_date'] >= now)
                and (qrow['disable_until'] is None 
                or qrow['disable_until'] < now)):
                # The quarantine found in this row is currently
                # active.
                quarantines.append(qrow['quarantine_type'])
        qh = Cerebrum.QuarantineHandler.QuarantineHandler(self.get_database(), quarantines)
        if qh.should_skip() or qh.is_locked():
            return True
        return False

registry.register_class(Entity)

# arch-tag: 1e0044b4-5c17-42a9-84f5-0b1013665681
