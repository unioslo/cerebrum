import Cerebrum.Account

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Builder import Builder, Attribute, Method
from Entity import Entity

from db import db

__all__ = ['Account', 'AccountAuthentication']

class Account(Entity):
    # hmm.. skipper np_type inntil videre. og konseptet rundt home/disk er litt føkka
    slots = Entity.slots + [Attribute('name', 'string', writable=True),
                            Attribute('owner_id', 'long'),
                            Attribute('create_date', 'Date'),
                            Attribute('creator_id', 'long'),
                            Attribute('expire_date', 'Date', writable=True)]
    methodSlots = [Method('get_authentications', 'AccountAuthentication')]

    cerebrum_class = Cerebrum.Account.Account
    
    def _load_account(self):
        e = Cerebrum.Account.Account(db)
        e.find(self._entity_id)

        self._name = e.account_name
        self._owner_id = int(e.owner_id)
        self._creator_id = int(e.creator_id)
        self._creator_date = e.create_date
        self._expire_date = e.expire_date

    load_name = load_owner_id = load_creator_id = load_create_date = load_expire_date = _load_account

    def get_authentications(self): # jada... dette skal bort/gjøres på en annen måte
        authentications = []
        for row in db.query('''SELECT account_id, method, auth_data
                               FROM account_authentication
                               WHERE account_id = %s''' % self._entity_id):
            authentications.append(AccountAuthentication.getByRow(row))
        return authentications

class AccountAuthentication(Builder):
    slots = [Attribute('account_id', 'Account'),
             Attribute('method', 'AuthenticationType'),
             Attribute('auth_data', 'string', writable=True)]

    def getByRow(cls, row):
        import Types
        account_id = int(row['account_id'])
        method = Types.AuthenticationType(int(row['method']))
        auth_data = row['auth_data']

        return cls(account_id=account_id,
                   method=method,
                   auth_data=auth_data)
    getByRow = classmethod(getByRow)

    def __repr__(self):
        return 'AccountAuthentication(account_id=%s, method=%s)' % (self._account_id, self._method)
