import Cerebrum.Person

from Cerebrum.extlib import sets

from Clever import Clever, LazyMethod, Lazy
from Node import Node
from Entity import Entity

from db import db

__all__ = ['Person', 'PersonName']

class PersonName(Node):
    slots = ['person', 'nameType', 'sourceSystem', 'name']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['name']

    def __init__(self, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, PersonName, *args, **vargs)

    def getKey(person, nameType, sourceSystem, *args, **vargs):
        return person, nameType, sourceSystem
    getKey = staticmethod(getKey)

    def load(self):
        raise Exception('FU')

    def loadParents(self):
        Node.loadParents(self)
        self._parents.add(self.entity)

    def __repr__(self):
        return '%s(person=%s, nameType=%s, sourceSystem=%s, name=%s)' % (self.__class__.__name__,
                                                                         self.person,
                                                                         self.nameType,
                                                                         self.sourceSystem,
                                                                         `self.name`)

Clever.prepare(PersonName, 'load')

class Person(Entity):
    # primaryAccount gir ingen mening
    # name gir bare navnet blant names som er fult navn (:P)
    # affiliations, quarantine med venner må implementeres
    slots = ['exportId', 'deceased', 'gender', 'contactInfo', 'accounts', 'name', 'names']
    readSlots = Entity.readSlots + slots
    writeSlots = Entity.writeSlots + ['exportId', 'deceased', 'gender']

    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Person, *args, **vargs)

    def load(self):
        import Types

        e = Cerebrum.Person.Person(db)
        e.find(self.id)

        self._exportId = e.export_id
        self._deceased = e.deceased == 'T' and True or False
        self._gender = Types.GenderType(int(e.gender))

    def loadChildren(self):
        Entity.loadChildren(self)

        self._children.update(self.accounts)
        self._children.update(self.names)

    def loadAccounts(self):
        import Account

        self._accounts = sets.Set()

        e = Cerebrum.Person.Person(db)
        e.entity_id = self.id
        
        for row in e.get_accounts():
            self._accounts.add(Account.Account(int(row['account_id'])))

    def loadNames(self):
        import Types

        e = Cerebrum.Person.Person(db)
        e.entity_id = self.id

        self._names = sets.Set()
        for row in e.get_all_names():
            nameType = Types.NameType(int(row['name_variant']))
            sourceSystem = Types.SourceSystem(int(row['source_system']))
            name = row['name']
            self._names.add(PersonName(person=self, nameType=nameType, sourceSystem=sourceSystem, name=name))

        self._name = ''
        for i in self._names:
            if i.nameType == Types.NameType.getByName('FULL'):
                self._name = i.name
                break

    getNames = LazyMethod('_names', 'loadNames')
    getName = LazyMethod('_name', 'loadNames')
    getAccounts = LazyMethod('_accounts', 'loadAccounts')
    getPrimaryAccount = LazyMethod('_primaryAccount', 'loadAccounts')

Clever.prepare(Person, 'load')
