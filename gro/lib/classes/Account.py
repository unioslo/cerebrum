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

import crypt

import Cerebrum.Account

from Builder import Attribute, Method
from CerebrumClass import CerebrumAttr

import Registry
registry = Registry.get_registry()

from Entity import Entity

__all__ = ['Account']

class Account(Entity):
    corba_parents = [Entity]
    slots = Entity.slots + [
        CerebrumAttr('name', str, 'account_name', write=True),
        CerebrumAttr('owner', Entity, 'owner_id'),
        CerebrumAttr('create_date', str),
        CerebrumAttr('creator', Entity, 'creator_id'),
        CerebrumAttr('expire_date', str, write=True)
    ]

    cerebrum_class = Cerebrum.Account.Account

registry.register_class(Account)

#def get_accounts(self):
#    s = registry.AccountSearch(self)
#    s.set_owner(self)
#    return s.search()

def get_accounts(self):
    e = Account.cerebrum_class(self.get_database())

    accounts = []
    for row in e.list_accounts_by_owner_id(self.get_id()):
        accounts.append(registry.Account(int(row['account_id'])))
    return accounts

Entity.register_method(Method('get_accounts', Account, sequence=True), get_accounts)
    
# arch-tag: 96b23dbe-d907-44f6-b6ac-a953ec3034e0
