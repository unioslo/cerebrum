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

from SpineLib.Builder import Method, Attribute
from SpineLib.DatabaseClass import DatabaseAttr

import CereUtils

from Entity import Entity
from Types import EntityType, AccountType
from Date import Date

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Account']

table = 'account_info'
class Account(Entity):
    slots = Entity.slots + [
        DatabaseAttr('owner', table, Entity),
        DatabaseAttr('owner_type', table, EntityType),
        DatabaseAttr('np_type', table, AccountType, optional=True),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('creator', table, Entity),
        DatabaseAttr('expire_date', table, Date),
        DatabaseAttr('description', table, Date),
        Attribute('name', str, write=True)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'account_id',
        'owner':'owner_id',
        'creator':'creator_id'
    }

    entity_type = EntityType(name='account')

    def load_name(self):
        entityName = registry.EntityName(self, registry.ValueDomain(name='account_names'))
        self._name = entityName.get_name()

cls = CereUtils.Factory.get('Account')
Account.save_name = CereUtils.create_save(Account.get_attr('name'), cls, 'account_name')
Account.save_expire_date = CereUtils.create_save(Account.get_attr('expire_date'), cls, 'description')

registry.register_class(Account)


def get_account_by_name(name):
    s = registry.EntityNameSearcher(name)
    s.set_value_domain(registry.ValueDomain(name='account_names'))
    s.set_name(name)

    account, = s.search()
    return account.get_entity()

# arch-tag: 166fa5e9-de27-4bb9-ad37-79f73fc4e102
