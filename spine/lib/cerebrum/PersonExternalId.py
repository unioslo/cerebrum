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
    s = registry.PersonExternalIdSearch()
    s.set_person(self)
    return s.search()

Person.register_method(Method('get_external_ids', [PersonExternalId]), get_external_ids)

# arch-tag: 6a0ecb31-a1a6-4581-ad50-c9e53323041b
