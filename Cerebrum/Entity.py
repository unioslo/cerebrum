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

# TODO: As PostgreSQL does not have any "schema" concept, the
#       "cerebrum." prefix to table names should only be used on
#       Oracle; currently, this is hardcoded.

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class Entity(DatabaseAccessor):
    """Class for generic access to Cerebrum entities.

    An instance of this class (or any of its subclasses) can associate
    with a Cerebrum entity.  Some of the methods defined here are not
    meaningful before such an association has been performed (TODO:
    raise exception?).

    """

    # Override this with separate type identifiers (e.g. 'p' for
    # Person) in each subclass.
    class_entity_type = None

    def __init__(self, database):
        """

        """
        super(Entity, self).__init__(database)
        self._clear()

    def _clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.entity_id = None
        self.entity_type = None

    ###
    ###   Methods dealing with the `cerebrum.entity_info' table
    ###

    def new(self, entity_type):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """
        new_id = self.nextval('cerebrum.entity_id_seq')
        self.execute("""
        INSERT INTO cerebrum.entity_info(entity_id, entity_type)
        VALUES (:1, :2)""", new_id, entity_type)
        return new_id

    def find(self, entity_id):
        """Associate the object with the entity whose identifier is ENTITY_ID.

        If ENTITY_ID isn't an existing entity identifier,
        NotFoundError is raised.

        """
        self.entity_id, self.entity_type = self.query_1("""
        SELECT entity_id, entity_type
        FROM cerebrum.entity_info
        WHERE entity_id=:1""", entity_id)

    def delete(self):
        "Completely remove an entity."
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self.execute("""
        DELETE cerebrum.entity_info WHERE entity_id=:1""", self.entity_id)
        self._clear()
        return

class EntityName(object):
    "Mixin class, usable alongside Entity for entities having names."
    def find_by_name(self, name, domain):
        "Associate instance with the entity having NAME in DOMAIN."
        entity_id = self.query_1("""
        SELECT entity_id
        FROM cerebrum.entity_name
        WHERE value_domain=:1 AND entity_name=:2""", domain, name)
        self.find(entity_id)

class EntityContactInfo(object):
    "Mixin class, usable alongside Entity for entities having contact info."
    def add_contact_info(self, source, type, value, pref=None,
                         description=None):
        # TODO: Calculate next available pref.  Should also handle the
        # situation where the provided pref is already taken.
        if pref is None:
            pref = 1
        self.execute("""
        INSERT INTO cerebrum.entity_contact_info
          (entity_id, source_system, contact_type, contact_pref,
           contact_value, description)
        VALUES (:1, :2, :3, :4, :5, :6)""",
                     self.entity_id, source, type, pref, value, description)

    def get_contact_info(self, source=None, contact=None):
        contacts = self.query("""
        SELECT * FROM cerebrum.entity_contact_info
        WHERE entity_id=:1""", self.entity_id)
        if source is not None:
            contacts = [c for c in contacts if c.source_system == source]
        if type is not None:
            contacts = [c for c in contacts if c.contact_type == type]
        return contacts

    def delete_contact_info(self, source, type, pref):
        self.execute("""
        DELETE cerebrum.entity_contact_info
        WHERE
          entity_id=:1 AND
          source_system=:2 AND
          contact_type=:3 AND
          contact_pref=:4""", self.entity_id, source, type, pref)

class EntityPhone(object):
    "Mixin class, usable alongside Entity for entities having phone nos."
    def add_entity_phone(self, source, type, phone, pref=None,
                         description=None):
        # TODO: Calculate next available pref.  Should also handle the
        # situation where the provided pref is already taken.
        if pref is None:
            pref = 1
        self.execute("""
        INSERT INTO cerebrum.entity_phone
          (entity_id, source_system, phone_type, phone_pref,
           phone_number, description)
        VALUES (:1, :2, :3, :4, :5, :6)""",
                     self.entity_id, source, type, pref, phone, description)

    def get_entity_phone(self, source=None, type=None):
        phones = self.query("""
        SELECT * FROM cerebrum.entity_phone
        WHERE entity_id=:1""", self.entity_id)
        if source is not None:
            phones = [c for c in phones if c.source_system == source]
        if type is not None:
            phones = [c for c in phones if c.phone_type == type]
        return phones

    def delete_entity_phone(self, source, type, pref):
        self.execute("""
        DELETE cerebrum.entity_phone
        WHERE
          entity_id=:1 AND
          source_system=:2 AND
          phone_type=:3 AND
          phone_pref=:4""", self.entity_id, source, type, pref)

class EntityAddress(object):
    "Mixin class, usable alongside Entity for entities having addresses."
    def add_entity_address(self, source, type, addr=None, pobox=None,
                           zip=None, city=None, country=None):
        pass

    def get_entity_address(self, source=None, type=None):
        pass

    def delete_entity_address(self, source, type):
        self.execute("""
        DELETE cerebrum.entity_address
        WHERE
          entity_id=:1 AND
          source_system=:2 AND
          address_type=:3""", self.entity_id, source, type)

class EntityQuarantine(object):
    "Mixin class, usable alongside Entity for entities we can quarantine."
    def add_entity_quarantine(self, type, creator, comment=None,
                              start=None, end=None):
        pass
    def get_entity_quarantine(self, type=None):
        pass

    def disable_entity_quarantine(self, type, until):
        pass

    def delete_entity_quarantine(self, type):
        self.execute("""
        DELETE cerebrum.entity_address
        WHERE
          entity_id=:1 AND
          quarantine_type=:2""", self.entity_id, type)
