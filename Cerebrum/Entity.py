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
import pprint

pp = pprint.PrettyPrinter(indent=4)

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
        self.const = Constants.Constants(database)
        self._debug_eq = False

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        # print "Entity.clear()"
        self.entity_id = None
        self.entity_type = None
        self._is_populated = False

        EntityAddress.clear(self)

    ###
    ###   Methods dealing with the `cerebrum.entity_info' table
    ###

    def populate(self, entity_type):
        "Set instance's attributes without referring to the Cerebrum DB."
        self.entity_type = entity_type
        self._is_populated = True
        self.__write_db = True

    def __eq__(self, other):
        assert isinstance(other, Entity)

        return True  # Allways true

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
            entity_id = self.nextval('entity_id_seq')
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_info] (entity_id, entity_type)
            VALUES (:e_id, :e_type)""", {'e_id' : entity_id, 'e_type': int(self.entity_type)})
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
        FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:e_id""", {'e_id' : entity_id})

    def delete(self):
        "Completely remove an entity."
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self.execute("""
        DELETE [:table schema=cerebrum name=entity_info] WHERE entity_id=:e_id""", {'e_id' : self.entity_id})
        self.clear()
        return


class EntityName(object):
    "Mixin class, usable alongside Entity for entities having names."
    def get_name(self, domain):
        return self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_name]
            WHERE entity_id=:e_id AND value_domain=:domain""",
                          {'e_id' : self.entity_id,
                          'domain' : int(domain)})

    def add_name(self, domain, name):
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_name]
          (entity_id, value_domain, entity_name)
        VALUES (:e_id, :domain, :name)""", {'e_id' : self.entity_id,
                                            'domain' : int(domain), 'name' : name})

    def delete_name(self, domain):
        return self.execute("""
        DELETE [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                            {'e_id' : self.entity_id, 'domain' : int(domain)})

    def find_by_name(self, domain, name):
        "Associate instance with the entity having NAME in DOMAIN."
        entity_id = self.query_1("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_name]
        WHERE value_domain=:domain AND entity_name=:name""",
                                 {'domain' : int(domain), 'name' : name})
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
        INSERT INTO [:table schema=cerebrum name=entity_contact_info]
          (entity_id, source_system, contact_type, contact_pref,
           contact_value, description)
        VALUES (:e_id, :source, :type, :pref, :value, :descript)""",
                     {'e_id' : self.entity_id, 'source' : source, 'type' : type,
                      'pref' : pref, 'value' : value, 'descript' : description})

    def get_contact_info(self, source=None, contact=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_contact_info]
            WHERE entity_id=:e_id""", {'e_id' : self.entity_id}),
            ('source_system', source),
            ('contact_type', type))

    def populate_contact_info(self, type, value, contact_pref=50, description=None):
        pass

    def delete_contact_info(self, source, type, pref):
        self.execute("""
        DELETE [:table schema=cerebrum name=entity_contact_info]
        WHERE entity_id=:e_id AND source_system=:s_system AND
          contact_type=:c_type AND contact_pref=:c_pref""",
                     {'e_id' : self.entity_id,
                      's_system' : source, 'c_type' : type, 'c_pref' : pref})


class EntityAddress(object):
    "Mixin class, usable alongside Entity for entities having addresses."

    def __init__(self):
        assert isinstance(Entity, self)
        self.clear()

    def __eq__(self, other):
        """Note: The object that affect_addresses has been called on
        must be on the left side of the equal sign, otherwise we don't
        really know what to compare."""
        
        if self._affect_source == None:
            return True
        assert isinstance(other, EntityAddress)

        for type in self._affect_types:
            try:
                if not self._compare_addresses(type, other):
                    return False
            except KeyError, msg:
                return False
        return True

    def _compare_addresses(self, type, other):
        """Returns True if addresses are equal.

        Raises KeyError with msg=MissingOther/MissingSelf if the
        corresponding object doesn't have this object type.

        self must be a populated object."""

        try:
            tmp = other.get_entity_address(self._affect_source, type)
            if len(tmp) == 0:
                raise KeyError
        except:
            raise KeyError, "MissingOther"

        other_addr = {'address_text' : tmp[0][3], 'p_o_box' : tmp[0][4],
                      'postal_number' : tmp[0][5], 'city' : tmp[0][6],
                      'country' : tmp[0][7]}
        try:
            ai = self._address_info[type]
        except:
            raise KeyError, "MissingSelf"
        
        # print "Compare: %s AND %s" % (ai, other_addr)
        for k in ('address_text', 'p_o_box', 'postal_number', 'city', 'country'):
            # print "compare: '%s' '%s'" % (ai[k], other_addr[k])
            if(ai[k] != other_addr[k]):
                return False
        return True

    def affect_addresses(self, source, *types):
        self._affect_source = source
        if types == None: raise "Not implemented"
        self._affect_types = types

    def populate_address(self, type, addr=None, pobox=None,
                         zip=None, city=None, country=None):
        self._address_info[type] = {'address_text' : addr, 'p_o_box' : pobox,
                                    'postal_number': zip, 'city' : city, 'country' : country}
        pass

    def write_db(self, as_object=None):
        # If affect_addresses has not been called, we don't care about
        # addresses
        if self._affect_source == None: return

        for type in self._affect_types:
            insert = False
            try:
                if not self._compare_addresses(type, as_object):
                    ai = self._address_info.get(type)
                    self.execute("""
                    UPDATE [:table schema=cerebrum name=entity_address]
                    SET address_text=:a_text, p_o_box=:p_box, postal_number=:p_num,
                        city=:city, country=:country
                    WHERE entity_id=:e_id AND source_system=:s_system AND
                        address_type=:a_type""",
                                 {'a_text' : ai['address_text'], 'p_box' : ai['p_o_box'],
                                  'p_num' : ai['postal_number'], 'city' : ai['city'],
                                  'country' : ai['country'], 'e_id' : as_object.entity_id,
                                  's_system' : int(self._affect_source), 'a_type' : int(type)})
            except KeyError, msg:
                # Note: the arg to a python exception must be casted to str :-(
                if str(msg) == "MissingOther":
                    self._add_entity_address(self._affect_source, type, **self._address_info[type])
                elif str(msg) == "MissingSelf":
                    self.execute("""DELETE [:table schema=cerebrum name=entity_address]
                                    WHERE entity_id=:e_id AND source_system=:s_system
                                          AND address_type=:a_type""",
                                 {'e_id' : as_object.entity_id,
                                  's_system' : int(self._affect_source),
                                  'a_type' : int(type)})
                else:
                    raise

    def clear(self):
        self._affect_source = None
        self._affect_types = None
        self._address_info = {}

    def _add_entity_address(self, source, type, address_text=None, p_o_box=None,
                           postal_number=None, city=None, country=None):
        #print "%s, %s, %s, %s, %s, %s, %s, %s, " % (self.entity_id, int(source), int(type),
        #             address_text, p_o_box, postal_number, city, country)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_address]
          (entity_id, source_system, address_type,
           address_text, p_o_box, postal_number, city, country)
        VALUES (:e_id, :s_system, :a_type, :a_text, :p_box, :p_num, :city, :country)""",
                     {'e_id' : self.entity_id, 's_system' : int(source), 'a_type' : int(type),
                      'a_text' : address_text, 'p_box' : p_o_box, 'p_num' : postal_number,
                      'city' : city, 'country' : country})

    def get_entity_address(self, source=None, type=None):
        # TODO: Select * gives positional args, which is error-prone: fix
        if self._is_populated:
            raise "is populated... Not implemented, and probably should not(?)"

        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_address]
            WHERE entity_id=:e_id""", {'e_id' : self.entity_id}),
            ('source_system', int(source)),
            ('address_type', int(type)))

    def delete_entity_address(self, source, type):
        self.execute("""
        DELETE [:table schema=cerebrum name=entity_address]
        WHERE
          entity_id=:e_id AND
          source_system=:s_system AND
          address_type=:a_type""", {'e_id' : self.entity_id, 's_system' : source,
                                    'a_type' : type})

class EntityQuarantine(object):
    "Mixin class, usable alongside Entity for entities we can quarantine."
    def add_entity_quarantine(self, type, creator, comment=None,
                              start=None, end=None):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_quarantine]
          (entity_id, quarantine_type,
           creator_id, comment, start_date, end_date)
        VALUES (:e_id, :q_type, :c_id, :comment, :start_date, :end_date)""",
                     {'e_id' : self.entity_id, 'q_type' : type,
                      'c_id' : creator, 'comment' : comment,
                      'start_date' : start, 'end_date' : end})

    def get_entity_quarantine(self, type=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_quarantine]
            WHERE entity_id=:e_id""", {'e_id' : self.entity_id}),
            ('quarantine_type', type))

    def disable_entity_quarantine(self, type, until):
        self.execute("""
        UPDATE [:table schema=cerebrum name=entity_quarantine]
        SET disable_until=:d_until
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id' : self.entity_id, 'q_type' : type, 'd_until' : until})

    def delete_entity_quarantine(self, type):
        self.execute("""
        DELETE [:table schema=cerebrum name=entity_quarantine]
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id' : self.entity_id, 'q_type' : type})
