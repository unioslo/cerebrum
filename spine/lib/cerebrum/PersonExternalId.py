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

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Person import Person
from Types import PersonExternalIdType, SourceSystem

from SpineLib import Registry
registry = Registry.get_registry()

table = 'person_external_id'
class PersonExternalId(DatabaseClass):
    primary = [
        DatabaseAttr('person', table, Person),
        DatabaseAttr('id_type', table, PersonExternalIdType),
        DatabaseAttr('source_system', table, SourceSystem),
    ]
    slots = [
        DatabaseAttr('external_id', table, str)
    ]

    db_attr_aliases = {
        table:{
            'person':'person_id'
        }
    }
        
registry.register_class(PersonExternalId)

def get_external_ids(self):
    s = registry.PersonExternalIdSearcher()
    s.set_person(self)
    return s.search()

Person.register_method(Method('get_external_ids', [PersonExternalId]), get_external_ids)

def add_external_id(self, id, id_type, source_system):
    obj = self._get_cerebrum_obj()
    obj.affect_external_id(source_system.get_id(), id_type.get_id())
    obj.populate_external_id(source_system.get_id(), id_type.get_id(), id)
    obj.write_db()

    # this is a hack to make sure all PersonName objects is up to date
    # maybe we should implement our own create/save
    for i in self.get_external_ids():
        i.get_external_id()
        del i._external_id

Person.register_method(Method('add_external_id', None, args=[('id', str), ('id_type', PersonExternalIdType), ('source_system', SourceSystem)], write=True), add_external_id)

# arch-tag: ee7aa1c8-845b-4ead-89e0-4fc7aa7051b6
