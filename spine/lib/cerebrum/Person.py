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
from SpineLib.Builder import Method

from Entity import Entity
from Date import Date
from Types import EntityType, GenderType
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

__all__ = ['Person']

# Convert deceased to be inserted into db.
def convert_to(value):
    if value:
        return 'T'
    else:
        return 'F'

# Convert deceased into boolean from a string.
def convert_from(value):
    if value == 'T':
        return True
    else:
        return False

table = 'person_info'
class Person(Entity):
    slots = Entity.slots + [
        DatabaseAttr('export_id', table, str, write=True),
        DatabaseAttr('birth_date', table, Date, write=True),
        DatabaseAttr('gender', table, GenderType, write=True),
        DatabaseAttr('deceased', table, bool, convert_from=convert_from, convert_to=convert_to, write=True),
        DatabaseAttr('description', table, str, write=True)
    ]

    method_slots = Entity.method_slots + [
        Method('delete', None, write=True)
    ]

    db_attr_aliases = Entity.db_attr_aliases.copy()
    db_attr_aliases[table] = {
        'id':'person_id'
    }

    entity_type = EntityType(name='person')

    def delete(self):
        db = self.get_database()
        person = Factory.get('Person')(db)
        person.find(self.get_id())
        person.delete()
        self.invalidate()

registry.register_class(Person)

def create(self, birthdate, gender):
    db = self.get_database()
    person = Factory.get('Person')(db)
    person.populate(birthdate.get_date, gender.get_name())
    person.write_db()
    return Person(person.entity_id, write_lock=self.get_writelock_holder())

Commands.register_method(Method('create_person', Person, write=True,
                         args=[('birthdate', Date), ('gender', GenderType)]), create)

# arch-tag: 7b2aca28-7bca-4872-98e1-c45e08faadfc
