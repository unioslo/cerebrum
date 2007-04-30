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

from SpineLib.DatabaseClass import DatabaseAttr
from SpineLib.Date import Date

from CerebrumClass import CerebrumAttr, CerebrumDbAttr

from OU import OU
from Entity import Entity
from Types import EntityType, GenderType, NameType, SourceSystem
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Person']

table = 'person_info'
class Person(Entity):
    slots = Entity.slots + (
        CerebrumDbAttr('export_id', table, str, write=True),
        CerebrumDbAttr('birth_date', table, Date, write=True),
        CerebrumDbAttr('gender', table, GenderType, write=True),
        CerebrumDbAttr('deceased_date', table, Date, write=True),
        CerebrumDbAttr('description', table, str, write=True)
    )

    Entity.db_attr_aliases[table] = {
        'id':'person_id'
    }
    cerebrum_attr_aliases = {}
    cerebrum_class = Factory.get('Person')
    entity_type = 'person'

registry.register_class(Person)

def _create_person(db, birthdate, gender, first_name, last_name, source_system):
    new_id = Person._create(db, birthdate.strftime('%Y-%m-%d'), gender.get_id())

    person = Person(db, new_id)

    first = NameType(db, name='FIRST')
    last = NameType(db, name='LAST')
    full = NameType(db, name='FULL')

    obj = person._get_cerebrum_obj()
    obj.affect_names(source_system.get_id(), first.get_id(), last.get_id(), full.get_id())
    obj.populate_name(first.get_id(), first_name)
    obj.populate_name(last.get_id(), last_name)
    obj.populate_name(full.get_id(), first_name + ' ' + last_name)
    obj.write_db()

    return person

def create_person(self, birthdate, gender, first_name, last_name, source_system):
    db = self.get_database()
    return _create_person(db, birthdate, gender, first_name, last_name, source_system)
create_person.signature = Person
create_person.signature_args = [Date, GenderType, str, str, SourceSystem]
create_person.signature_write = True

Commands.register_methods([create_person])

def ou_create_person(self, birthdate, gender, first_name, last_name, source_system, affiliation, status):
    """
    Normal users should only be able to create a person affiliated to an ou.
    """
    db = self.get_database()
    person = _create_person(db, birthdate, gender, first_name, last_name, source_system)
    obj = person._get_cerebrum_obj()
    obj.populate_affiliation(source_system.get_id(), self.get_id(), affiliation, status)
    obj.write_db()
    return person
ou_create_person.signature = Person
ou_create_person.signature_name = 'create_person'
ou_create_person.signature_args = [Date, GenderType, str, str, SourceSystem, int, int]
ou_create_person.signature_write = True
OU.register_methods([ou_create_person])

# arch-tag: 7b2aca28-7bca-4872-98e1-c45e08faadfc
