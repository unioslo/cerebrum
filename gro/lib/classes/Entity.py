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

import Registry
registry = Registry.get_registry()

Builder = registry.Builder
Attribute = registry.Attribute
Method = registry.Method

CerebrumClass = registry.CerebrumClass
CerebrumAttr = registry.CerebrumAttr
CerebrumTypeAttr = registry.CerebrumTypeAttr

EntityAuth = registry.EntityAuth

EntityType = registry.EntityType

__all__ = ['Entity', 'Note', 'Address', 'ContactInfo']

class Entity(Builder, CerebrumClass, EntityAuth):
    primary = [CerebrumAttr('entity_id', 'long')]
    slots = primary + [
        CerebrumTypeAttr('entity_type', 'EntityType', type_class=EntityType)]
    method_slots = Builder.method_slots + [
        Method('get_spreads', 'SpreadSeq'),
        Method('get_notes', 'NoteSeq'),
        Method('get_contact_info', 'ContactInfoSeq'),
        Method('get_addresses', 'AddressSeq'),
        Method('add_note', 'void', [('subject', 'string'), ('description', 'string')], write=True)]

    cerebrum_class = Cerebrum.Entity.Entity

    def add_note(self, subject, description):
        db = self.get_database()
        e = Cerebrum.modules.Note.EntityNote(db)
        e.entity_id = self.get_entity_id()

        print 'change_by', [db.change_by]

        e.add_note(db.change_by, subject, description)

    def __new__(cls, *args, **vargs):
        obj = Builder.__new__(Entity, *args, **vargs)

        if obj.__class__ is Entity: # this is a fresh object
            obj.__init__(*args, **vargs)

        entity_type = obj.get_entity_type()
        entity_class = entity_type.get_class()

        if cls is not entity_class and cls is not Entity:
            raise Exception('wrong class. Asked for %s, but found %s' % (cls, entity_class))
        else:
            obj.__class__ = entity_class

        return obj

    def build_methods(cls):
        super(Entity, cls).build_methods()
        super(Builder, cls).build_methods()

    build_methods = classmethod(build_methods)

    def get_spreads(self):
        e = Cerebrum.Entity.Entity(self.get_database())
        e.entity_id = self.get_entity_id()
        
        spreads = []
        for i in e.get_spread():
            spreads.append(registry.Spread(id=int(i[0])))
            
        return spreads

    def get_notes(self):
        notes = []

        e = Cerebrum.modules.Note.EntityNote(self.get_database())
        e.entity_id = self.get_entity_id()

        for row in e.get_notes():
            row = dict(row._items())
            row['entity_id'] = self._entity_id
            notes.append(Note.getByRow(row))

        return notes
           
    def get_addresses(self):
        addresses = []
        e = Cerebrum.Entity.EntityAddress(self.get_database())
        e.entity_id = self.get_entity_id()

        for row in e.get_entity_address():
            addresses.append(Address.getByRow(row))

        return addresses

    def get_contact_info(self):
        contact_info = []

        e = Cerebrum.Entity.EntityContactInfo(self.get_database())
        e.entity_id = self._entity_id

        for row in e.get_contact_info():
            contact_info.append(ContactInfo.getByRow(row))

        return contact_info

    def is_quarantined(self):
        account = Cerebrum.Entity.EntityQuarantine(self.get_database())
        account.entity_id = self._entity_id

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

class ContactInfo(Builder):
    primary = [Attribute('entity_id', 'long'),
               Attribute('source_system', 'SourceSystem'),
               Attribute('contact_type', 'ContactInfoType'),
               Attribute('contact_pref', 'long')]
    slots = primary + [Attribute('contact_value', 'string', write=True),
                       Attribute('description', 'string', write=True)]

    def getByRow(cls, row):
        contactInfo = cls(entity_id=int(row['entity_id']),
                          source_system=registry.SourceSystem(id=int(row['source_system'])),
                          contact_type=registry.ContactInfoType(id=int(row['contact_type'])),
                          contact_pref=int(row['contact_pref']),
                          contact_value=row['contact_value'],
                          description=row['description'])
        return contactInfo
    getByRow = classmethod(getByRow)

    # hat. hvorfor kan ikke cerebrum ha en unik id pr entitet? (ja. en
    # kontaktinfo burde være en entitet).
    # hadde det ikke vært mer fornuftig å hatt entity, contactPref som
    # primær-nøkkel? nå blir det jo bare rot.
    def create_primary_key(entity_id, source_system, contact_type, *args, **vargs):
        return entity_id, source_system, contact_type
    create_primary_key = staticmethod(create_primary_key)

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
    # Address skal vel kanskje heller ikke ha write-attributes?
    slots = [Attribute('entity_id', 'long'),
             Attribute('source_system', 'SourceSystem'),
             Attribute('address_type', 'AddressType'),
             Attribute('address_text', 'string', write=True), 
             Attribute('p_o_box', 'string', write=True),
             Attribute('postal_number', 'string', write=True),
             Attribute('city', 'string', write=True),
             Attribute('country', 'long', write=True)]

    def getByRow(cls, row):
        return cls(entity_id=int(row['entity_id']),
                   source_system=registry.SourceSystem(id=int(row['source_system'])),
                   address_type=registry.AddressType(id=int(row['address_type'])),
                   address_text=row['address_text'],
                   p_o_box=row['p_o_box'],
                   postal_number=row['postal_number'],
                   city=row['city'],
                   country=int(row['country']))
