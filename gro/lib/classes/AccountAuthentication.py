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
        DatabaseAttr('account', table, Account),
        DatabaseAttr('method', table, AuthenticationType)
    ]
    slots = [
        DatabaseAttr('auth_data', table, str, write=True)
    ]

    db_attr_aliases = {
        table:{
            'account':'account_id'
        }
    }

registry.register_class(AccountAuthentication)

def get_authentications(self):
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

# arch-tag: bb277dd2-3474-4891-8666-5fe9a096b735
