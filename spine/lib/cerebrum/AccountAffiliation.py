# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError

from Account import Account
from Entity import Entity
from OU import OU
from Person import Person
from Types import PersonAffiliationType

from SpineLib import Registry
registry = Registry.get_registry()

table = 'account_type'
class AccountAffiliation(DatabaseClass):
    primary = (
        DatabaseAttr('person', table, Person),
        DatabaseAttr('ou', table, OU),
        DatabaseAttr('affiliation', table, PersonAffiliationType),
        DatabaseAttr('account', table, Account),
    )

    slots = (
        DatabaseAttr('priority', table, int),
    )

    db_attr_aliases = {
        table:{
            'ou':'ou_id',
            'account':'account_id',
            'person':'person_id',
        }
    }

    def get_auth_entity(self):
        return self.get_account()
    get_auth_entity.signature = Entity
registry.register_class(AccountAffiliation)

def set_affiliation(self, ou, affiliation, priority):
    obj = self._get_cerebrum_obj()
    obj.set_account_type(ou.get_id(), affiliation.get_id(), priority)
    obj.write_db()
set_affiliation.signature = None
set_affiliation.signature_args = [OU, PersonAffiliationType, int]
set_affiliation.signature_write = True
Account.register_methods([set_affiliation])

def remove_affiliation(self, ou, affiliation):
    obj = self._get_cerebrum_obj()
    obj.del_account_type(ou.get_id(), affiliation.get_id())
    obj.write_db()
remove_affiliation.signature = None
remove_affiliation.signature_args = [OU, PersonAffiliationType]
remove_affiliation.signature_write = True
Account.register_methods([remove_affiliation])

def get_affiliations(self):
    s = registry.AccountAffiliationSearcher(self.get_database())
    s.set_account(self)
    return s.search()
get_affiliations.signature = [AccountAffiliation]
get_affiliations.signature_args = []
Account.register_methods([get_affiliations])
