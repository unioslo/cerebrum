import Cerebrum.Entity

from Clever import Clever, LazyMethod, Lazy
from Node import Node
from Cerebrum.gro.Cerebrum_core import Errors

from db import db

__all__ = ['AddressType', 'ContactInfoType', 'GenderType', 'EntityType',
           'SourceSystem', 'NameType', 'AuthenticationType', 'Spread',
           'GroupMemberOperationType']

class CodeType(Node):
    slots = ['id', 'name', 'description']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + []

    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        assert type(id) == int
        Node.__init__(self, parents, children)
        Clever.__init__(self, CodeType, id, *args, **vargs)

    def getKey(id, *args, **vargs):
        return id

    def getByName(cls, name):
        rows = db.query('''SELECT code, description
                           FROM %s WHERE code_str = %s''' % (cls._tableName, `name`)) # ugh. stygg escaping
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (cls.__name__, name))
        row = rows[0]

        id = int(row['code'])
        description = row['description']

        return cls(id, name=name, description=description)

    getByName = classmethod(getByName)
    getKey = staticmethod(getKey)

    def load(self):
        rows = db.query('''SELECT code_str, description
                           FROM %s WHERE code = %s''' % (self._tableName, self.id))
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (self.__class__.__name__, self.id))
        row = rows[0]

        self._name = row['code_str']
        self._description = row['description']

Clever.prepare(CodeType, 'load')

class AddressType(CodeType):
    _tableName = 'address_code'

class ContactInfoType(CodeType):
    _tableName = 'contact_info_code'

    def loadChildren(self):
        import Entity

        CodeType.loadChildren(self)
        for row in db.query('''SELECT entity_id, source_system, contact_type,
                                      contact_pref, contact_value, description
                               FROM entity_contact_info WHERE contact_type = %s''' % self.id):
            self._children.add(Entity.ContactInfo.getByRow(row))

class GenderType(CodeType):
    _tableName = 'gender_code'

    def loadChildren(self):
        import Person

        CodeType.loadChildren(self)
        for row in db.query('''SELECT person_id
                               FROM person_info WHERE gender = %s''' % self.id):
            self._children.add(Person.Person(int(row['person_id'])))

Clever.prepare(GenderType, 'load')

class EntityType(CodeType):
    _tableName = 'entity_type_code'

    slots = []

    def loadChildren(self):
        import Entity

        CodeType.loadChildren(self)
        
        e = Cerebrum.Entity.Entity(db)
        self._children.update([Entity.Entity(int(i[0])) for i in e.list_all_with_type(self.id)])

    def getClass(self):
        import Group, Account, Person, Host, Disk

        if self.name == 'group':
            return Group.Group
        elif self.name == 'account':
            return Account.Account
        elif self.name == 'person':
            return Person.Person
        elif self.name == 'host':
            return Host.Host
        elif self.name == 'disk':
            return Disk.Disk
        else:
            raise NotImplementedError('Class is not implemented')

Clever.prepare(EntityType, 'load')

class SourceSystem(CodeType):
    _tableName = 'authoritative_system_code'

class NameType(CodeType):
    _tableName = 'person_name_code'

class AuthenticationType(CodeType):
    _tableName = 'authentication_code'

    def loadChildren(self):
        import Account

        CodeType.loadChildren(self)
        
        for row in db.query('''SELECT account_id, method, auth_data
                               FROM account_authentication
                               WHERE method = %s''' % self.id):
            self._children.add(Account.AccountAuthentication.getByRow(row))

class GroupMemberOperationType(CodeType):
    _tableName = 'group_membership_op_code'

class GroupVisibilityType(CodeType):
    _tableName = 'group_visibility_code'

class QuarantineType(CodeType):
    # her driter jeg i feltet duration inntil videre....
    _tableName = 'quarantine_code'

class Spread(CodeType):
    _tableName = 'spread_code'
    slots = CodeType.slots + ['entityType'] # skjønner ikke hvorfor de har med entityType egentlig...
    readSlots = [] + slots
    writeSlots = CodeType.writeSlots + []

    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Clever.__init__(self, Spread, id, *args, **vargs)

    def load(self):
        rows = db.query('''SELECT code_str, entity_type, description
                           FROM spread_code WHERE code = %s''' % self.id)
        if not rows:      
            raise Errors.NoSuchNodeError('spread %s not found' % self.id)
        row = rows[0]     
                          
        self._entityType = EntityType(int(row['entity_type']))
        self._name = row['code_str']
        self._description = row['description']

    def loadChildren(self):
        import Entity

        CodeType.loadChildren(self)

        e = Cerebrum.Entity.Entity(db)
        self._children.update([Entity(int(i[0])) for i in e.list_all_with_spread(self.id)])

Clever.prepare(Spread, 'load')
