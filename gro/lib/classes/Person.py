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

from Cerebrum.extlib import sets
from GroBuilder import GroBuilder
from Builder import Attribute, Method
from Searchable import Searchable
from CerebrumClass import CerebrumAttr, CerebrumTypeAttr, \
                          CerebrumDateAttr, CerebrumBooleanAttr

import Registry
registry = Registry.get_registry()

Entity = registry.Entity

GenderType = registry.GenderType

__all__ = ['Person', 'PersonName']

class Person(Entity):
    # primaryAccount gir ingen mening
    # name gir bare navnet blant names som er fult navn (:P)
    # affiliations, quarantine med venner må implementeres
    slots = Entity.slots + [CerebrumAttr('export_id', 'string'),
                            CerebrumDateAttr('birth_date', 'Date', write=True),
                            CerebrumBooleanAttr('deceased', 'boolean', write=True),
                            CerebrumTypeAttr('gender', 'GenderType', GenderType, write=True),
                            CerebrumAttr('description', 'string', write=True)]
    method_slots = Entity.method_slots + [
        Method('get_accounts','AccountSeq'),
        Method('get_names','PersonNameSeq')]

    cerebrum_class = Cerebrum.Person.Person

    def get_accounts(self):
        accounts = []

        e = Cerebrum.Person.Person(self.get_database())
        e.entity_id = self._entity_id
        
        for row in e.get_accounts():
            accounts.append(registry.Account(int(row['account_id'])))
        return accounts

    def get_names(self):
        names = []

        e = Cerebrum.Person.Person(self.get_database())
        e.entity_id = self._entity_id

        for row in e.get_all_names():
            name_variant = registry.NameType(id=int(row['name_variant']))
            source_system = registry.SourceSystem(id=int(row['source_system']))
            name = row['name']
            names.append(PersonName(self, name_variant, source_system, name))

        return names

class PersonName(GroBuilder, Searchable):
    primary = [Attribute('person', 'Person'), Attribute('name_variant', 'NameType'),
               Attribute('source_system', 'SourceSystem'), Attribute('name', 'string')]
    slots = primary + []

    def create_search_method(cls):
        def search(self, person=None, name_variant=None, source_system=None, name=None):
            def prepare_string(value):
                value = value.replace("*", "%")
                value = value.replace("?", "_")
                value = value.lower()
                return value

            where = []
            if person is not None:
                where.append('person_id = %i' % person)
            if name_variant is not None:
                where.append('name_variant = %i' % name_variant.get_id())
            if source_system is not None:
                where.append('source_system = %i' % source_system.get_id())
            if name is not None:
                where.append('LOWER(name) LIKE :name')
                name = prepare_string(name)
            
            if where:
                where = 'WHERE %s' % ' AND '.join(where)
            else:
                where = ''

            objects = []
            db = self.get_database()
            for row in db.query("""SELECT person_id, name_variant, source_system, name
                                   FROM [:table schema=cerebrum name=%s]
                                   %s""" % ("person_name", where), {'name': name}):
                person = registry.Person(entity_id=int(row['person_id']))
                name_variant = registry.NameType(id=int(row['name_variant']))
                source_system = registry.SourceSystem(id=int(row['source_system']))
                name = row['name']
                objects.append(cls(person=person, name_variant=name_variant,
                                   source_system=source_system, name=name))
            return objects
        return search
    create_search_method = classmethod(create_search_method)

# arch-tag: 73b26bd2-5c22-455a-bccd-4eb8a03fc9f1
