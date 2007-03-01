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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.SpineExceptions import NotFoundError, TooManyMatchesError

from Person import Person
from Types import NameType, SourceSystem

from SpineLib import Registry
registry = Registry.get_registry()

class PersonName(DatabaseClass):
    primary = (
        DatabaseAttr('person', 'person_name', Person),
        DatabaseAttr('name_variant', 'person_name', NameType),
        DatabaseAttr('source_system', 'person_name', SourceSystem),
    )
    slots = (
        DatabaseAttr('name', 'person_name', str, write=True),
    )
    db_attr_aliases = {
        'person_name':{
            'person':'person_id'
        }
    }
        
registry.register_class(PersonName)

def get_names(self):
    s = registry.PersonNameSearcher(self.get_database())
    s.set_person(self)
    return s.search()
get_names.signature = [PersonName]

def set_name(self, name, name_type, source_system):
    obj = self._get_cerebrum_obj()
    obj.affect_names(source_system.get_id(), name_type.get_id())
    obj.populate_name(name_type.get_id(), name)
    obj.write_db()

    # this is a hack to make sure all PersonName objects is up to date
    # maybe we should implement our own create/save
    # TODO: Is this needed?
    for i in self.get_names():
        i.get_name()
        del i._name
set_name.signature = None
set_name.signature_args = [str, NameType, SourceSystem]
set_name.signature_write = True

def remove_name(self, name_type, source_system):
    obj = self._get_cerebrum_obj()
    obj._delete_name(source_system.get_id(), name_type.get_id())
remove_name.signature = None
remove_name.signature_args = [NameType, SourceSystem]
remove_name.signature_write = True

def get_name(self, name_type, source_system):
    db = self.get_database()
    return PersonName(db, self, name_type, source_system).get_name()
get_name.signature = str
get_name.signature_args = [NameType, SourceSystem]
get_name.signature_exceptions= [NotFoundError]


def get_cached_full_name(self):
    db = self.get_database()
    cached = SourceSystem(db, name='Cached')
    full = NameType(db, name='FULL')
    return PersonName(db, self, full, cached).get_name()
get_cached_full_name.signature = str
get_cached_full_name.signature_exceptions= [NotFoundError]

    

Person.register_methods([remove_name, set_name, get_names, get_cached_full_name, get_name])

# arch-tag: 6a0ecb31-a1a6-4581-ad50-c9e53323041b
