import Cerebrum.Entity
import Cerebrum.modules.Note

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Clever import Clever, LazyMethod, Lazy
from Node import Node

from db import db

__all__ = ['Entity', 'Note']

class Entity(Node):
    slots = ['id', 'entityType', 'spreads', 'notes', 'contactInfo', 'addresses']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + []

    def __new__(cls, *args, **vargs):
        key = Entity, cls.getKey(*args, **vargs)
        
        if key in cls.cache:
            self = cls.cache[key]
            if not (issubclass(self.__class__, cls) or issubclass(cls, self.__class__)):
                raise Exception('Wrong class. Asked for %s, but found %s' % (cls, self.__class__))
            return self

        self = object.__new__(Entity)
        Entity.__init__(self, *args, **vargs)

        try:
            real = self.entityType.getClass()
            if not (issubclass(real, cls) or issubclass(cls, real)):
                raise Exception('Wrong class. Asked for %s, but found %s' % (cls, real))
        except NotImplementedError:
            real = Entity
        self.__class__ = real
        self._key = key
        cls.cache[key] = self
        return self

    def getKey(id, *args, **vargs):
        return id
    getKey = staticmethod(getKey)

    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, Entity, id, *args, **vargs)

    def create(entityType):
# Det funker ikke pga log_change.
#        e = Cerebrum.Entity.Entity(db)
#        e.populate(entityType.id)
#        e.write_db()
#        id = e.entity_id

        id = int(db.nextval('entity_id_seq'))
        db.execute('''INSERT INTO entity_info
                        (entity_id, entity_type)
                        VALUES (%s, %s)''' % (id, entityType.id))
        # changelog her...

        return Entity(id, entityType=entityType)
    create = staticmethod(create)

    # load methods
    
    def load(self):
        e = Cerebrum.Entity.Entity(db)
        e.find(self.id)
        
        from Types import EntityType
        self._entityType = EntityType(int(e.entity_type))

    def loadParents(self):
        Node.loadParents(self)

        self._parents.update(self.spreads)
        self._parents.add(self.entityType)

    def loadSpreads(self):
        import Types
        self._spreads = sets.Set()
        e = Cerebrum.Entity.Entity(db)
        e.entity_id = self.id

        self._spreads.update(sets.Set([Types.Spread(int(i[0])) for i in e.get_spread()]))

    def loadChildren(self):
        Node.loadChildren(self)

        self._children.update(self.notes)
        self._children.update(self.contactInfo)

    def loadNotes(self):
        self._notes = sets.Set()

        e = Cerebrum.modules.Note.EntityNote(db)
        e.entity_id = self.id

        for row in e.get_notes():
            self._notes.add(Note(id = int(row['note_id']),
                                    createDate = row['create_date'],
                                    creator = Entity(int(row['creator_id'])),
                                    subject = row['subject'],
                                    description = row['description']))

    def loadAddresses(self):
        self._addresses = sets.Set()
        e = Cerebrum.Entity.EntityAddress(db)
        e.entity_id = self.id

        for row in e.get_entity_address():
            self._addresses.add(Address.getByRow(row))

    def loadContactInfo(self):
        self._contactInfo = sets.Set()

        e = Cerebrum.Entity.EntityContactInfo(db)
        e.entity_id = self.id

        for row in e.get_contact_info():
            self._contactInfo.add(ContactInfo.getByRow(row))
    
    # properties

    getNotes = LazyMethod('_notes', 'loadNotes')
    getSpreads = LazyMethod('_spreads', 'loadSpreads')
    getContactInfo = LazyMethod('_contactInfo', 'loadContactInfo')
    getAddresses = LazyMethod('_addresses', 'loadAddresses')


Clever.prepare(Entity, 'load')

class ContactInfo(Node):
    slots = ['entity', 'sourceSystem', 'contactInfoType', 'contactPref', 'contactValue', 'description']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['contactPref', 'contactValue', 'description']

    def __init__(self, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, ContactInfo, *args, **vargs)

    def getByRow(cls, row):
        import Types

        entity = Entity(int(row['entity_id']))
        sourceSystem = Types.SourceSystem(int(row['source_system']))
        contactInfoType = Types.ContactInfoType(int(row['contact_type']))
        contactPref = int(row['contact_pref'])
        contactValue = row['contact_value']
        description  = row['description']

        contactInfo = cls(entity=entity,
                          sourceSystem=sourceSystem,
                          contactInfoType=contactInfoType,
                          contactPref=contactPref,
                          contactValue=contactValue,
                          description=description)
        return contactInfo
    getByRow = classmethod(getByRow)

    # hat. hvorfor kan ikke cerebrum ha en unik id pr entitet? (ja. en kontaktinfo er en entitet).
    # hadde det ikke vært mer fornuftig å hatt entity, contactPref som primær-nøkkel?
    # nå blir det jo bare rot.
    def getKey(entity, sourceSystem, contactInfoType, contactPref, *args, **vargs):
        return entity, sourceSystem, contactInfoType, contactPref
    getKey = staticmethod(getKey)

    def __repr__(self):
        return 'ContactInfo(entity=%s, sourceSystem=%s, contactInfoType=%s, contactPref=%s)' % (self.entity, self.sourceSystem, self.contactInfoType, self.contactPref)

    def load(self):
        rows = db.query('''SELECT contact_value, description
                           FROM entity_contact_info
                           WHERE entity_id = %s
                           AND   source_system = %s
                           AND   contact_type = %s
                           AND   contact_pref = %s''' % (`self.entity`,`self.sourceSystem`,`self.contactType`,`self.contactPref`))
        if not rows:
            raise Errors.NoSuchNodeError('ContactInfoType %s not found' % self.id)
        row = rows[0]

        self._contactValue = row['contaact_value']
        self._description = row['description']

Clever.prepare(ContactInfo, 'load')


class Note(Node):
    slots = ['id', 'createDate', 'creator', 'entity', 'subject', 'description']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['subject', 'description'] # hmm. Note er kanskje immutable?
    
    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, Note, id, *args, **vargs)

    def create(creator, entity, subject, description):
        id = int(db.nextval('note_seq'))
        db.execute('''INSERT INTO note
                      (note_id, creator_id, entity_id, subject, description)
                      VALUES (%s, %s, %s, %s, %s)''' % (id, creator.id, entity.id, `subject`, `description`))
        db.commit()
        return Note(id, creator=creator, entity=entity, subject=subject, description=description)
    create = staticmethod(create)
    db.commit()

    def getKey(id, *args, **vargs):
        return id
    getKey = staticmethod(getKey)

    def loadParents(self):
        Node.loadParents(self)

        self._parents.add(self.entity)

    def load(self):
        rows = db.query('''SELECT create_date, creator_id, entity_id, subject, description
                           FROM note WHERE note_id = %s''' % self.id)
        if not rows:
            raise Errors.NoSuchNodeError('Note %s not found' % self.id)
        row = rows[0]

        self._createDate = row['create_date']
        self._creator = Entity(int(row['creator_id']))
        self._entity = Entity(int(row['entity_id']))
        self._subject = row['subject']
        self._description = row['description']

Clever.prepare(Note, 'load')

class Address(Node):
    # country må fikses..
    slots = ['entity', 'sourceSystem', 'addressType', 'text', 'poBox', 'postalNumber', 'city', 'country']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['text', 'poBox', 'postalNumber', 'city', 'country']

    def __init__(self, parents, children, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, Address, *args, **vargs)

    def getByRow(cls, row):
        import Types

        entity = Entity(int(row['entity_id']))
        sourceSystem = Types.SourceSystem(int(row['source_system']))
        addressType = Types.AddressType(int(row['address_type']))
        text = row['address_text']
        poBox = row['p_o_box']
        postalNumber = row['postal_number']
        city = row['city']
        country = int(row['country'])

        return cls(entity=entity, sourceSystem=sourceSystem, addressType=addressType, text=text,
                   poBox=poBox, postalNumber=postalNumber, city=city, country=county)

    def getKey(entity, sourceSystem, addressType, *args, **vargs):
        return entity, sourceSystem, addressType

    def load(self):
        raise Exception('FU')

Clever.prepare(Address, 'load')
