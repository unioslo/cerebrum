import crypt

from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Account import Account
from Types import AuthenticationType

import Registry
registry = Registry.get_registry()

table = 'account_authentication'

class AccountAuthentication(DatabaseClass):
    primary = [
        DatabaseAttr('account', table, Account, dbattr_name='account_id'),
        DatabaseAttr('method', table, AuthenticationType)
    ]
    slots = [
        DatabaseAttr('auth_data', table, str, write=True)
    ]

registry.register_class(AccountAuthentication)

def get_authentications(self): # jada... dette skal bort/gjøres på en annen måte
    s = registry.AccountAuthenticationSearch(self)
    s.set_account(self)

    return s.search()
Account.register_method(Method('get_authentications', AccountAuthentication, sequence=True), get_authentications)

def authenticate(self, password):
    # FIXME: pass på her altså. Det er mange forskjellige typer.
    for auth in get_authentications(self):
        auth_data = auth.get_auth_data()
        if auth_data == crypt.crypt(password, auth_data):
            return True
    return False

Account.register_method(Method('authenticate', bool, [('password', 'string')]), authenticate)
