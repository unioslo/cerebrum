# Copyright 2002 University of Oslo, Norway
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

"""

"""

from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityPhone, EntityAddress, EntityQuarantine

ENTITY_TYPE_PERSON = 'p'

class PersonName(object):
    "Mixin class for Person"

    def get_person_name_codes(self):
        return self.query("SELECT code, description FROM person_name_code")

    def get_name(self, variant, source_system=None):
        """TODO: It is uncertain wheter source_system=None is legal"""
        qry = "SELECT name FROM person_name WHERE person_id=:1 AND name_variant=:2"
        params = (self.person_id, variant)
        if source_system != None:
            qry += " AND source_system=:3"
            params += (source_system,)
        return self.query_1(qry, *params)

    def set_name(self, variant, source_system, name):
        self.execute("""
        INSERT INTO cerebrum.person_name (person_id, name_variant, source_system, name)
        VALUES (:1, :2, :3, :4)""", self.person_id, variant, source_system, name)

class PersonAffiliation(object):
    "Mixin class for Person"
    def get_affiliation(self, variant, source_system=None):
        pass

    def set_affiliation(self, ou_id, affiliation, status='valid'):
        self.execute("""
        INSERT INTO cerebrum.person_affiliation (person_id, ou_id, affiliation, status,
                    create_date, last_date)
        VALUES (:1, :2, :3, :4, SYSDATE, SYSDATE)""", self.person_id, ou_id, affiliation,
                     status)

class Person(Entity, EntityContactInfo, EntityPhone, EntityAddress,
             EntityQuarantine, PersonName, PersonAffiliation):
    
    def new(self, birth_date, gender, description=None):
        """Register a new person.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """

        new_id = super(Person, self).new(ENTITY_TYPE_PERSON)
        self.execute("""
        INSERT INTO cerebrum.person_info (entity_type, person_id, export_id, birth_date,
                                      gender, deceased, description)
        VALUES (:1, :2, :3, :4, :5, :6, :7)""", ENTITY_TYPE_PERSON, new_id,
                     'exp-'+str(new_id), birth_date, gender, 'F', description)
        
        return new_id

    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        (self.person_id, self.export_id, self.birth_date, self.gender,
         self.deceased, self.description) = self.query_1(
            """SELECT person_id, export_id, birth_date, gender,
                      deceased, description
               FROM cerebrum.person_info
               WHERE person_id=:1 """, person_id)

    def set_external_id(self, id_type, external_id):
        self.execute("""
        INSERT INTO cerebrum.person_external_id(person_id, id_type, external_id)
        VALUES (:1, :2, :3)""", self.person_id, id_type, external_id)

        pass

    def find_by_external_id(self, id_type, external_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM cerebrum.person_external_id
        WHERE id_type=:1 AND external_id=:2""",
                                 id_type, external_id)
        self.find(person_id)
        return person_id
