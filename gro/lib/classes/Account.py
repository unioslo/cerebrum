# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import Cerebrum.Account
import crypt

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
    method_slots = Entity.method_slots + [Method('get_authentications', 'AccountAuthentication')]

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

    def authenticate(self, password):
        e = Cerebrum.Account.Account(db)

        for auth in self.get_authentications():
            auth_data = auth.get_auth_data()
            if auth_data == crypt.crypt(password, auth_data):
                return True
        return False

class AccountAuthentication(Builder):
    primary = [Attribute('account_id', 'Account'),
               Attribute('method', 'AuthenticationType')]
    slots = primary + [Attribute('auth_data', 'string', writable=True)]

    def getByRow(cls, row):
        import Types
        account_id = int(row['account_id'])
        method = Types.AuthenticationType(int(row['method']))
        auth_data = row['auth_data']

        return cls(account_id=account_id,
                   method=method,
                   auth_data=auth_data)
    getByRow = classmethod(getByRow)
