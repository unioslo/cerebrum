import Cerebrum.Account

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Clever import Clever, LazyMethod, Lazy
from Node import Node
from Entity import Entity

from db import db

__all__ = ['Account', 'AccountAuthentication']

class Account(Entity):
    # hmm.. skipper np_type inntil videre. og konseptet rundt home/disk er litt føkka
    slots = ['name', 'owner', 'createDate', 'creator', 'home', 'disk', 'expireDate', 'authentications']
    readSlots = Entity.readSlots + slots
    writeSlots = Entity.writeSlots + ['name', 'home', 'disk', 'expireDate']
    
    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Account, *args, **vargs)

    def load(self):
        import Disk
        e = Cerebrum.Account.Account(db)
        e.find(self.id)

        self._name = e.account_name
        self._owner = Entity(int(e.owner_id))
        self._creator = Entity(int(e.creator_id))
        self._createDate = e.create_date
        self._expireDate = e.expire_date

    def loadParents(self):
        Entity.loadParents(self)

        self._parents.add(self.owner)

    def loadAuthentications(self):
        self._authentications = sets.Set()
        for row in db.query('''SELECT account_id, method, auth_data
                               FROM account_authentication
                               WHERE account_id = %s''' % self.id):
            self._authentications.add(AccountAuthentication.getByRow(row))

    getAuthentications = LazyMethod('_authentications', 'loadAuthentications')

Clever.prepare(Account, 'load')

class AccountAuthentication(Node):
    slots = ['account', 'authenticationType', 'data']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['data']

    def __init__(self, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, AccountAuthentication, *args, **vargs)

    def getByRow(cls, row):
        import Types
        account = Account(int(row['account_id']))
        authenticationType = Types.AuthenticationType(int(row['method']))
        data = row['auth_data']

        return cls(account=account, authenticationType=authenticationType, data=data)
    getByRow = classmethod(getByRow)

    def getKey(account, authenticationType, *args, **vargs):
        return account, authenticationType
    getKey = staticmethod(getKey)

    def load(self):
        rows = db.query('''SELECT auth_data
                           FROM account_authentication
                           WHERE account_id = %s
                           AND   method = %s''' % (self.account.id, self.authenticationType))
        if not rows:
            raise Errors.NoSuchNodeError('%s %s not found' % (cls.__name__, name))

        self._data = row['auth_data']

    def __repr__(self):
        return 'AccountAuthentication(account=%s, authenticationType=%s)' % (self.account, self.authenticationType)

Clever.prepare(AccountAuthentication, 'load')
