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

import Cerebrum.Person

from Cerebrum.extlib import sets

from Builder import Builder, Attribute, Method
from Entity import Entity

from db import db

__all__ = ['Person', 'PersonName']

class Person(Entity):
    # primaryAccount gir ingen mening
    # name gir bare navnet blant names som er fult navn (:P)
    # affiliations, quarantine med venner må implementeres
    slots = Entity.slots + [Attribute('export_id', 'string'),
                            Attribute('birth_date', 'Date'),
                            Attribute('deceased', 'boolean'),
                            Attribute('gender', 'GenderType'),
                            Attribute('description', 'string')]

    cerebrum_class = Cerebrum.Person.Person

    def load(self):
        import Types

        e = Cerebrum.Person.Person(db)
        e.find(self._entity_id)

        self._exportId = e.export_id
        self._birth_date = e.birth_date
        self._deceased = e.deceased == 'T' and True or False
        self._gender = Types.GenderType(int(e.gender))

    def get_accounts(self):
        import Account

        accounts = []

        e = Cerebrum.Person.Person(db)
        e.entity_id = self._entity_id
        
        for row in e.get_accounts():
            accounts.append(Account.Account(int(row['account_id'])))
        return accounts

    def get_names(self):
        import Types

        names = []

        e = Cerebrum.Person.Person(db)
        e.entity_id = self._entity_id

        for row in e.get_all_names():
            name_variant = Types.NameType(int(row['name_variant']))
            source_system = Types.SourceSystem(int(row['source_system']))
            name = row['name']
            names.append(PersonName(person_id=self._entity_id, name_variant=name_variant, source_system=source_system, name=name))

        return names

class PersonName(Builder):
    slots = [Attribute('person_id', 'long'),
             Attribute('name_variant', 'NameType'),
             Attribute('source_system', 'SourceSystem'),
             Attribute('name', 'string')]

    def __repr__(self):
        return '%s(person_id=%s, name_variant=%s, source_system=%s, name=%s)' % (self.__class__.__name__,
                                                                         self._person_id,
                                                                         self._name_variant,
                                                                         self._source_system,
                                                                         `self._name`)
