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

import cereconf
from Cerebrum.Utils import Factory
from SpineLib.Builder import Attribute
from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError, TooManyMatchesError
from SpineLib.Date import Date

from CerebrumClass import CerebrumClass, CerebrumAttr, CerebrumDbAttr
from Cerebrum.Utils import Factory

from Entity import Entity, ValueDomainHack
from Types import EntityType, AccountType
from Cerebrum.spine.Commands import Commands
from Cerebrum.spine.Group import Group
from Cerebrum.spine.Person import Person

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Account']

table = 'account_info'
class Account(Entity):
    """This class represents an account. The account is an Entity, and thus has
    the same attributes as the Entity. In addition, it has the following attributes:
        owner - The entity that owns the account
        owner_type - The type of the entity that owns the account
        np_type - The type of the account itself
        create_date - The date on which the account was created
        creator - The entity which created the account
        expire_date - The date on which the account expires
        description - A short description of the account
        name - The name of the account
    \\see Entity
    \\see EntityType
    \\see AccountType
    """

    slots = Entity.slots + (
        CerebrumDbAttr('owner', table, Entity),
        CerebrumDbAttr('owner_type', table, EntityType),
        CerebrumDbAttr('np_type', table, AccountType, write=True),
        CerebrumDbAttr('create_date', table, Date),
        CerebrumDbAttr('creator', table, Entity),
        CerebrumDbAttr('expire_date', table, Date, write=True),
        DatabaseAttr('description', table, str, write=True),
        CerebrumDbAttr('name', 'entity_name', str, write=True)
    )
    
    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'account_id',
        'owner':'owner_id',
        'creator':'creator_id'
    }
    db_constants = Entity.db_constants.copy()
    db_constants['entity_name'] = ValueDomainHack('account')

    cerebrum_attr_aliases = {'name':'account_name'}
    cerebrum_class = Factory.get('Account')

    entity_type = 'account'
registry.register_class(Account)

def is_expired(self):
    obj = self._get_cerebrum_obj()
    return obj.is_expired()
is_expired.signature = bool
Account.register_methods([is_expired])

def _create_account(db, name, owner, np_type, expire_date):
    expire_date = expire_date and expire_date._value or None
    np_type = np_type and np_type.get_id() or None
    owner_type = owner.get_type().get_id()
    owner_id = owner.get_id()
    new_id = Account._create(db, name, owner_type, owner_id, np_type, db.change_by, expire_date)
    return Account(db, new_id)

def create_person_account(self, name, expire_date):
    """
    Create a new account.
    \\param name Name of the account.
    \\param expire_date Date on which the account will expire.
    \\return Created Account object.
    """
    db = self.get_database()
    return _create_account(db, name, self, None, expire_date)
create_person_account.signature = Account
create_person_account.signature_args = [str, Date]
create_person_account.signature_write = True
create_person_account.signature_name = 'create_account'
Person.register_methods([create_person_account])


def create_group_account(self, name, np_type, expire_date):
    """
    Create a new non-personal account.
    \\param name Name of the account.
    \\param np_type Non-personal AccountType
    \\param expire_date Date on which the account will expire.
    \\return Created Account object.
    """
    db = self.get_database()
    return _create_account(db, name, self, np_type, expire_date)
create_group_account.signature = Account
create_group_account.signature_args = [str, AccountType, Date]
create_group_account.signature_write = True
create_group_account.signature_name = 'create_account'
Group.register_methods([create_group_account])


def create_account(self, name, owner, expire_date):
    """
    Create a new account.
    \\param name Name of the account.
    \\param owner Entity that owns the account, usually a Person.
    \\param expire_date Date on which the account will expire.
    \\return Created Account object.
    """
    print 'WARNING: Commands.create_account is deprecated.'
    db = self.get_database()
    return _create_account(db, name, owner, None, expire_date)
create_account.signature = Account
create_account.signature_args = [str, Entity, Date]
create_account.signature_write = True
Commands.register_methods([create_account])

def get_primary_account(self):
    account_id = self._get_cerebrum_obj().get_primary_account()
    if account_id is None:
        return None
    return Account(self.get_database(), account_id)
get_primary_account.signature = Account
get_primary_account.signature_name = 'get_primary_account'
Person.register_methods([get_primary_account])

def create_np_account(self, name, owner, np_type, expire_date):
    """
    Create a new non-personal account.
    \\param name Name of the account.
    \\param owner Entity that owns the account, usually a Group.
    \\param np_type Non-personal AccountType
    \\param expire_date Date on which the account will expire.
    \\return Created Account object.
    """
    print 'WARNING: Commands.create_np_account is deprecated.'
    db = self.get_database()
    return _create_account(db, name, owner, np_type, expire_date)
create_np_account.signature = Account
create_np_account.signature_args = [str, Entity, AccountType, Date]
create_np_account.signature_write = True
Commands.register_methods([create_np_account])

def get_account_by_name(self, name):
    """
    Get an account by name.
    \\param name The name of the account to get.
    \\return The Account object with the given name.
    """

    db = self.get_database()

    s = registry.EntityNameSearcher(db)
    value_domain = cereconf.ENTITY_TYPE_NAMESPACE['account']
    s.set_value_domain(registry.ValueDomain(db, name=value_domain))
    s.set_name(name)

    accounts = s.search()
    if len(accounts) == 0:
        raise NotFoundError('There are no accounts with the name %s' % name)
    elif len(accounts) > 1:
        raise TooManyMatchesError('There are several accounts with the name %s' % name)
    return accounts[0].get_entity()

get_account_by_name.signature = Account
get_account_by_name.signature_args = [str]
get_account_by_name.signature_exceptions = [NotFoundError, TooManyMatchesError]
Commands.register_methods([get_account_by_name])

def get_accounts(self):
    """
    Get all accounts owned by this entity.
    
    \\return A list of all Account objects owned by this entity.

    \\see Account
    """

    s = registry.AccountSearcher(self.get_database())
    s.set_owner(self)
    return s.search()

get_accounts.signature = [Account]
Entity.register_methods([get_accounts])

def suggest_usernames(self, first_name, last_name):
    """
    Suggest usernames for an account.

    \\param first_name The first name of the person for which the username should be suggested.
    \\param last_name The last name of the person for which the username should be suggested.

    \\return A list of the suggested usernames as strings.

    \\see Account
    \\see Person
    """

    db = self.get_database()
    account = Factory.get('Account')(db)
    value_domain = cereconf.ENTITY_TYPE_NAMESPACE['account']
    return account.suggest_unames(registry.ValueDomain(db, name=value_domain).get_id(), first_name, last_name)

suggest_usernames.signature = [str]
suggest_usernames.signature_args = [str, str]
Commands.register_methods([suggest_usernames])

# arch-tag: 166fa5e9-de27-4bb9-ad37-79f73fc4e102
