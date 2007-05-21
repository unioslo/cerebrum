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

from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr
from SpineLib.Date import Date

from CerebrumClass import CerebrumClass, CerebrumAttr, CerebrumDbAttr

from OU import OU
from Person import Person
from Entity import Entity
from Types import PersonAffiliationType, SourceSystem
from PersonAffiliationStatus import PersonAffiliationStatus

from SpineLib import Registry
registry = Registry.get_registry()

table = 'person_affiliation_source'
class PersonAffiliation(DatabaseClass):
    primary = (
        DatabaseAttr('person', table, Person),
        DatabaseAttr('ou', table, OU),
        DatabaseAttr('affiliation', table, PersonAffiliationType),
        DatabaseAttr('source_system', table, SourceSystem),
    )
    slots = (
        DatabaseAttr('status', table, PersonAffiliationStatus, write=True),
        DatabaseAttr('description', table, str, write=True),
        DatabaseAttr('create_date', table, Date),
        DatabaseAttr('last_date', table, Date),
        DatabaseAttr('deleted_date', table, Date),
    )

    db_attr_aliases = {
        table : {
            'person':'person_id',
            'ou' : 'ou_id'
        }
    }

    def set_status(self, status):
        person = self.get_person()
        obj = person._get_cerebrum_obj()
        obj.add_affiliation(self.get_ou().get_id(), self.get_affiliation().get_id(), self.get_source_system().get_id(), status.get_id())
        obj.write_db()
    set_status.signature = None
    set_status.signature_args = [PersonAffiliationStatus]
    set_status.signature_write = True

    def delete(self):
        db = self.get_database()
        person = Factory.get('Person')(db)
        person.find(self.get_person().get_id())
        person.delete_affiliation(self.get_ou().get_id(), self.get_affiliation().get_id(), self.get_source_system().get_id())
        person.write_db()
    delete.signature = None
    delete.signature_write = True

    def marked_for_deletion(self):
        """Checks if the affiliation deleted_date is set."""
        if self.get_deleted_date() is not None:
            return True
        else:
            return False
    marked_for_deletion.signature = bool

    def get_auth_entity(self):
        return self.get_person()
    get_auth_entity.signature = Entity
registry.register_class(PersonAffiliation)

def add_affiliation(self, ou, affiliation_status, source_system):
    db = self.get_database()
    person = Factory.get('Person')(db)
    person.find(self.get_id())
    person.add_affiliation(ou.get_id(), affiliation_status.get_affiliation().get_id(), source_system.get_id(), affiliation_status.get_id())
    person.write_db()
    return PersonAffiliation(db, self, ou, affiliation_status.get_affiliation(), source_system)
add_affiliation.signature = PersonAffiliation
add_affiliation.signature_args = [OU, PersonAffiliationStatus, SourceSystem]
add_affiliation.signature_write = True

def get_affiliations(self):
    s = registry.PersonAffiliationSearcher(self.get_database())
    s.set_person(self)
    return s.search()
get_affiliations.signature = [PersonAffiliation]

Person.register_methods([add_affiliation, get_affiliations])

# arch-tag: 848f642e-e7d7-11d9-8ba0-fa7bc076c927
