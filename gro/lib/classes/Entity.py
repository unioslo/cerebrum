import Cerebrum.Entity
import Cerebrum.modules.Note

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute, Method

from db import db

__all__ = ['Entity', 'Note']

class Entity(Builder):
    primary = [Attribute('entity_id', 'long')]
    slots = [Attribute('entity_id', 'long'),
             Attribute('entity_type', 'EntityType')]
    methodSlots = [Method('get_spreads', 'SpreadSeq'),
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
        e.entity_id = self.get_entity_id

        for row in e.get_contact_info():
            contact_info.append(ContactInfo.getByRow(row))

        return contact_info

    def __repr__(self):
        return '%s(entity_id=%s)' % (self.__class__.__name__, self._entity_id)
    
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
    def getKey(entity_id, source_system, contact_type, *args, **vargs):
        return entity_id, source_system, contact_type
    getKey = staticmethod(getKey)

    def __repr__(self):
        return 'ContactInfo(entity_id=%s, source_system=%s, contact_type=%s)' % (self._entity_id, self._source_system, self._contact_type)

class Note(Builder):
    primary = [Attribute('note_id', 'long')]
    slots = primary + [Attribute('create_date', 'Date'),
                       Attribute('creator_id', 'long'),
                       Attribute('entity_id', 'long'),
                       Attribute('subject', 'string'),
                       Attribute('description', 'string')]
    
    def getByRow(cls, row):
        return cls(entity_id=int(row['note_id']),
                   create_date=row['create_date'],
                   creator_id=int(row['creator_id']),
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
