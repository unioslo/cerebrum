import Cerebrum.Person

from Cerebrum.extlib import sets
from Cerebrum.gro.Utils import Cached, Lazy, LazyMethod, Clever

from Node import Node
from Entity import Entity

db = Cerebrum.Utils.Factory.get('Database')()

class PersonName(Node):
    slots = ['person', 'nameType', 'sourceSystem', 'name']
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
    slots = ['exportId', 'deceased', 'gender', 'contactInfo', 'accounts', 'affiliations',
             'address', 'quarantine', 'name', 'names', 'primaryAccount']
    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Person, *args, **vargs)

    def load(self):
        e = Cerebrum.Person.Person(db)
        e.find(self.id)

        self._exportId = e.export_id
        self._deceased = e.deceased == 'T' and True or False
        self._gender = GenderType(int(e.gender))

    def loadChildren(self):
        import Account

        Entity.loadChildren(self)

        e = Cerebrum.Person.Person(db)
        e.entity_id = self.id
        
        # tihi. unødvendige mye kode
        for row in e.get_accounts():
            account = Account.Account(int(row['account_id']))
            if self._primaryAccount is Lazy:
                self._primaryAccount = account
            self._children.add(account)
        if self._primaryAccount is Lazy:
            self._primaryAccount = None

        self._children.update(self.names)

    def loadNames(self):
        e = Cerebrum.Person.Person(db)
        e.entity_id = self.id

        self._names = sets.Set()
        for row in e.get_all_names():
            nameType = NameType(int(row['name_variant']))
            sourceSystem = SourceSystem(int(row['source_system']))
            name = row['name']
            self._names.add(PersonName(person=self, nameType=nameType, sourceSystem=sourceSystem, name=name))

        self._name = None
        for i in self._names:
            if i.nameType == NameType.getByName('FULL'):
                self._name = i.name
                break

    def getAccounts(self):
        import Account

        return sets.Set(filter(lambda a:isinstance(a, Account.Account), self.children))

    getNames = LazyMethod('_names', 'loadNames')
    getName = LazyMethod('_name', 'loadNames')
    getPrimaryAccount = LazyMethod('_primaryAccount', 'loadChildren')

    primaryAccount = property(getPrimaryAccount)

Clever.prepare(Person, 'load')


