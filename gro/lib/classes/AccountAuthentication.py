# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
    s = registry.AccountAuthenticationSearcher(self)
    s.set_account(self)

    return s.search()
Account.register_method(Method('get_authentications', [AccountAuthentication]), get_authentications)

def authenticate(self, password):
    # FIXME: pass på her altså. Det er mange forskjellige typer.
    for auth in get_authentications(self):
        auth_data = auth.get_auth_data()
        if auth_data == crypt.crypt(password, auth_data):
            return True
    return False

Account.register_method(Method('authenticate', bool, [('password', str)]), authenticate)

# arch-tag: bb277dd2-3474-4891-8666-5fe9a096b735
