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
from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute, Method
from Searchable import Searchable

from db import db

__all__ = ['Entity', 'Note', 'Address', 'ContactInfo']

class Entity(Builder, Searchable):
    primary = [Attribute('entity_id', 'long')]
    slots = [Attribute('entity_id', 'long'),
             Attribute('entity_type', 'EntityType')]
    method_slots = [Method('get_spreads', 'SpreadSeq'),
                    Method('get_notes', 'NoteSeq'),
                    Method('get_contact_info', 'ContactInfoSeq'),
                    Method('get_addresses', 'AddressSeq')]

#    primary = [Attribute('entity_id', 'long')]
#    slots = primary + [Attribute('entity_type', 'long'),
#                       Method('get_notes', 'NoteSeq'),
#                       Method('add_note',
#                              'void',
#                              (('subject', 'string'), ('description', 'string')),
#                              apNode=True)]

#    def add_note(self, creator_id, subject, description):
#        e = Cerebrum.modules.Note.EntityNote(db)
#        e.entity_id = self.get_entity_id()
#
#        e.add_note(creator_id, subject, description)

    cerebrum_class = Cerebrum.Entity.Entity

    def get_spreads(self):
        import Types
        e = Cerebrum.Entity.Entity(db)
        e.entity_id = self.get_entity_id()
        
        spreads = []
        for i in e.get_spread():
            spreads.append(Types.Spread(int[0]))
            
        return spreads

    def get_notes(self):
        notes = []

        e = Cerebrum.modules.Note.EntityNote(db)
        e.entity_id = self.get_entity_id()

        for row in e.get_notes():
            row = dict(row._items())
            row['entity_id'] = self._entity_id
            notes.append(Note.getByRow(row))

        return notes
           
    def get_addresses(self):
        addresses = []
        e = Cerebrum.Entity.EntityAddress(db)
        e.entity_id = self.get_entity_id()

        for row in e.get_entity_address():
            addresses.append(Address.getByRow(row))

        return addresses

    def get_contact_info(self):
        contact_info = []

        e = Cerebrum.Entity.EntityContactInfo(db)
        e.entity_id = self._entity_id

        for row in e.get_contact_info():
            contact_info.append(ContactInfo.getByRow(row))

        return contact_info

    def is_quarantined(self):
        account = Cerebrum.Entity.EntityQuarantine(db)
        account.entity_id = self._entity_id

        # koka fra bofhd
        quarantines = []      # TBD: Should the quarantine-check have a utility-API function?
        now = db.DateFromTicks(time.time())
        for qrow in account.get_entity_quarantine():
            if (qrow['start_date'] <= now
                and (qrow['end_date'] is None or qrow['end_date'] >= now)
                and (qrow['disable_until'] is None 
                or qrow['disable_until'] < now)):
                # The quarantine found in this row is currently
                # active.
                quarantines.append(qrow['quarantine_type'])
        qh = Cerebrum.QuarantineHandler.QuarantineHandler(db, quarantines)
        if qh.should_skip() or qh.is_locked():
            return True
        return False

class ContactInfo(Builder):
    primary = [Attribute('entity_id', 'long'),
               Attribute('source_system', 'SourceSystem'),
               Attribute('contact_type', 'ContactInfoType'),
               Attribute('contact_pref', 'long')]
    slots = primary + [Attribute('contact_value', 'string', writable=True),
                       Attribute('description', 'string', writable=True)]

    def getByRow(cls, row):
        import Types

        contactInfo = cls(entity_id=int(row['entity_id']),
                          source_system=Types.SourceSystem(int(row['source_system'])),
                          contact_type=Types.ContactInfoType(int(row['contact_type'])),
                          contact_pref=int(row['contact_pref']),
                          contact_value=row['contact_value'],
                          description=row['description'])
        return contactInfo
    getByRow = classmethod(getByRow)

    # hat. hvorfor kan ikke cerebrum ha en unik id pr entitet? (ja. en
    # kontaktinfo burde være en entitet).
    # hadde det ikke vært mer fornuftig å hatt entity, contactPref som
    # primær-nøkkel? nå blir det jo bare rot.
    def get_key(entity_id, source_system, contact_type, *args, **vargs):
        return entity_id, source_system, contact_type
    get_key = staticmethod(get_key)

class Note(Builder):
    primary = [Attribute('note_id', 'long')]
    slots = primary + [Attribute('create_date', 'Date'),
                       Attribute('creator_id', 'long'),
                       Attribute('entity_id', 'long'),
                       Attribute('subject', 'string'),
                       Attribute('description', 'string')]
    
    def getByRow(cls, row):
        return cls(note_id=int(row['note_id']),
                   create_date=row['create_date'],
                   creator_id=int(row['creator_id']),
                   entity_id=int(row['entity_id']),
                   subject=row['subject'],
                   description=row['description'])

    getByRow = classmethod(getByRow)

class Address(Builder):
    # country må fikses.. Lage en egen Node for det i Types kanskje..
    slots = [Attribute('entity_id', 'long'),
             Attribute('source_system', 'SourceSystem'),
             Attribute('address_type', 'AddressType'),
             Attribute('address_text', 'string', writable=True), 
             Attribute('p_o_box', 'string', writable=True),
             Attribute('postal_number', 'string', writable=True),
             Attribute('city', 'string', writable=True),
             Attribute('country', 'long', writable=True)]

    def getByRow(cls, row):
        import Types

        return cls(entity_id=int(row['entity_id']),
                   source_system=Types.SourceSystem(int(row['source_system'])),
                   address_type=Types.AddressType(int(row['address_type'])),
                   address_text=row['address_text'],
                   p_o_box=row['p_o_box'],
                   postal_number=row['postal_number'],
                   city=row['city'],
                   country=int(row['country']))
