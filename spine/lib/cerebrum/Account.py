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

from Cerebrum.Utils import Factory
from SpineLib.Builder import Method, Attribute
from SpineLib.DatabaseClass import DatabaseAttr

from CerebrumClass import CerebrumClass, CerebrumAttr, CerebrumDbAttr
from Cerebrum.Utils import Factory

from Entity import Entity
from Types import EntityType, AccountType
from Date import Date
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Account']

table = 'account_info'
class Account(Entity):
    slots = Entity.slots + [
        CerebrumDbAttr('owner', table, Entity),
        CerebrumDbAttr('owner_type', table, EntityType),
        CerebrumDbAttr('np_type', table, AccountType, write=True),
        CerebrumDbAttr('create_date', table, Date),
        CerebrumDbAttr('creator', table, Entity),
        CerebrumDbAttr('expire_date', table, Date, write=True),
        CerebrumDbAttr('description', table, str, write=True),
        CerebrumAttr('name', str, write=True)
    ]
    method_slots = Entity.method_slots + [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'account_id',
        'owner':'owner_id',
        'creator':'creator_id'
    }

    cerebrum_attr_aliases = {'name':'account_name'}
    cerebrum_class = Factory.get('Account')

    entity_type = EntityType(name='account')

    def delete(self):
        db = self.get_database()
        account = Factory.get('Account')(db)
        account.find(self.get_id())
        account.delete()
        self.invalidate()

registry.register_class(Account)

def create_account(self, name, owner, expire_date):
    db = self.get_database()
    account = Factory.get('Account')(db)
    account.populate(name, owner.get_type().get_id(), owner.get_id(), None, db.change_by, expire_date._value)
    account.write_db()
    return Account(account.entity_id, write_lock=self.get_writelock_holder())

args = [('name', str), ('owner', Entity), ('expire_date', Date)]
Commands.register_method(Method('create_account', Account, args=args, write=True), create_account)

def get_account_by_name(name):
    s = registry.EntityNameSearcher()
    s.set_value_domain(registry.ValueDomain(name='account_names'))
    s.set_name(name)

    account, = s.search()
    return account.get_entity()

def get_accounts(self):
    s = registry.AccountSearcher()
    s.set_owner(self)
    return s.search()

Entity.register_method(Method('get_accounts', [Account]), get_accounts)

def suggest_unames(self, domain, first_name, last_name):
    account = Factory.get('Account')(self.get_database())
    return account.suggest_unames(domain.get_id(), first_name, last_name)

Commands.register_method(Method('suggest_unames', [str], args=[('domain', registry.ValueDomain), ('first_name', str), ('last_name', str)]), suggest_unames)

# arch-tag: 166fa5e9-de27-4bb9-ad37-79f73fc4e102
