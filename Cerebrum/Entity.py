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
from Cerebrum import Utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants

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
        self.clear()
        self.__write_db = False
        self.constants = Constants.Constants(database)

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        print "Entity.clear()"
        self.entity_id = None
        self.entity_type = None

        EntityAddress.clear(self)

    ###
    ###   Methods dealing with the `cerebrum.entity_info' table
    ###

    def populate(self, entity_type):
        "Set instance's attributes without referring to the Cerebrum DB."
        self.entity_type = entity_type
        self.__write_db = True

    def __eq__(self, other):
        assert isinstance(other, Entity)
        return other.entity_type == self.entity_type

    def write_db(self, as_object=None):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If `as_object' isn't specified (or is None), the instance is
        written as a new entry to the Cerebrum database.  Otherwise,
        the object overwrites the Entity entry corresponding to the
        instance `as_object'.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        """

        assert self.__write_db
        if as_object is None:
            entity_id = self.nextval('cerebrum.entity_id_seq')
            self.execute("""
            INSERT INTO cerebrum.entity_info(entity_id, entity_type)
            VALUES (:1, :2)""", entity_id, int(self.entity_type))
        else:
            entity_id = as_object.entity_id
            # Don't need to do anything as entity type can't change
        self.entity_id = entity_id
        self.__write_db = False

    def new(self, entity_type):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """
        Entity.populate(self, entity_type)
        Entity.write_db(self)
        Entity.find(self, self.entity_id)
        return self.entity_id

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
        self.clear()
        return


class EntityName(object):
    "Mixin class, usable alongside Entity for entities having names."
    def get_name(self, domain=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM cerebrum.entity_name
            WHERE entity_id=:1""", self.entity_id),
            ('value_domain', domain))

    def add_name(self, domain, name):
        return self.execute("""
        INSERT INTO cerebrum.entity_name
          (entity_id, value_domain, entity_name)
        VALUES (:1, :2, :3)""", self.entity_id, domain, name)

    def delete_name(self, domain):
        return self.execute("""
        DELETE cerebrum.entity_name
        WHERE entity_id=:1 AND value_domain=:1""", self.entity_id, domain)

    def find_by_name(self, domain, name):
        "Associate instance with the entity having NAME in DOMAIN."
        entity_id = self.query_1("""
        SELECT entity_id
        FROM cerebrum.entity_name
        WHERE value_domain=:1 AND entity_name=:2""", domain, name)
        Entity.find(self, entity_id)

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
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM cerebrum.entity_contact_info
            WHERE entity_id=:1""", self.entity_id),
            ('source_system', source),
            ('contact_type', type))

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
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM cerebrum.entity_phone
            WHERE entity_id=:1""", self.entity_id),
            ('source_system', source),
            ('phone_type', type))

    def delete_entity_phone(self, source, type, pref):
        self.execute("""
        DELETE cerebrum.entity_phone
        WHERE
          entity_id=:1 AND
          source_system=:2 AND
          phone_type=:3 AND
          phone_pref=:4""", self.entity_id, source, type, pref)

## p = CerebrumFactory.Person()
## p2 = CerebrumFactory.Person()
## for person in LT.persons():
##     p.clear()
##     p.affect_addresses(Constants.source_LT, Constants.address_street,
##                        Constants.address_post)
##     for addr in person.get_addresses():
##         p.populate_address(addr)
##     try:
##         p2.find_fnr(person.get_fnr())
##         if p <> p2:
##             p.write_db(p2)
##     except NotFound:
##         p.write_db()

# Må kunne signalisere tre forskjellige typer operasjoner som følge av
# at write_db() kalles: add, change og delete.
#
# Må ha signalisert til ea1 hvilke(t?) source_system-innslag som er
# interessante for sammenlikningen (og dermed også for write_db()).
#
# Fint med mulighet til å signalisere hvilken/hvilke adresse-typer som
# skal tas med under sammenlikningen (og av write_db()).
    

class EntityAddress(object):
    "Mixin class, usable alongside Entity for entities having addresses."

    def __init__(self):
        assert isinstance(Entity, self)
        self.clear()

    def affect_addresses(self, source, *types):
        self._affect_source = source
        if types == None: raise "Not implemented"
        self._affect_types = types

    def populate_address(self, type, addr=None, pobox=None,
                         zip=None, city=None, country=None):
        self._address_info[type] = (addr, pobox, zip, city, country)
        pass

    def write_db(self, as_object=None):
        # If affect_addresses has not been called, we don't care about
        # addresses
        if self._affect_source == None: return
        print "EntityAddress.write_db()"

        for type in self._affect_types:
            insert = False
            if as_object == None:
                if self._address_info.has_key(type):
                    insert = True
            else:
                try:
                    as_object.get_entity_address(self._affect_source, type)
                    if not self._address_info.has_key(type):
                        # Delete
                        pass
                    else:
                        # Update (compare first?)
                        pass
                except:
                    insert = True
            if insert:
                self._add_entity_address(self._affect_source, type, *self._address_info[type])


    def clear(self):
        # print "EntityAddress.clear()"
        self._affect_source = None
        self._affect_types = None
        self._address_info = {}

    def _add_entity_address(self, source, type, addr=None, pobox=None,
                           zip=None, city=None, country=None):
        self.execute("""
        INSERT INTO cerebrum.entity_address
          (entity_id, source_system, address_type,
           address_text, p_o_box, postal_number, city, country)
        VALUES (:1, :2, :3, :4, :5, :6, :7, :8)""",
                     self.entity_id, int(source), int(type),
                     addr, pobox, zip, city, country)

    def get_entity_address(self, source=None, type=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM cerebrum.entity_address
            WHERE entity_id=:1""", self.entity_id),
            ('source_system', source),
            ('address_type', type))

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
        self.execute("""
        INSERT INTO cerebrum.entity_quarantine
          (entity_id, quarantine_type,
           creator_id, comment, start_date, end_date)
        VALUES (:1, :2, :3, :4, :5, :6)""",
                     self.entity_id, type,
                     creator, comment, start, end)

    def get_entity_quarantine(self, type=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM cerebrum.entity_quarantine
            WHERE entity_id=:1""", self.entity_id),
            ('quarantine_type', type))

    def disable_entity_quarantine(self, type, until):
        self.execute("""
        UPDATE cerebrum.entity_quarantine
        SET disable_until=:3
        WHERE
          entity_id=:1 AND
          quarantine_type=:2
        """, self.entity_id, type, until)

    def delete_entity_quarantine(self, type):
        self.execute("""
        DELETE cerebrum.entity_quarantine
        WHERE
          entity_id=:1 AND
          quarantine_type=:2""", self.entity_id, type)
