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

import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory

class Entity(DatabaseAccessor):
    """Class for generic access to Cerebrum entities.

    An instance of this class (or any of its subclasses) can associate
    with a Cerebrum entity.  Some of the methods defined here are not
    meaningful before such an association has been performed (TODO:
    raise exception?).

    """

    __metaclass__ = Utils.mark_update

    __read_attr__ = ('__in_db', 'const',
                     # TBD: HM *thinks* these attributes should be
                     # write-once...
                     'entity_id')
    __write_attr__ = ('entity_type',)
    dontclear = ('const',)

    def __init__(self, database):
        """

        """
        super(Entity, self).__init__(database)
        self.clear()
        self.const = Factory.getConstants()(database)

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        for attr in Entity.__read_attr__:
            if hasattr(self, attr):
                if attr not in self.dontclear:
                    delattr(self, attr)
        for attr in Entity.__write_attr__:
            if attr not in self.dontclear:
                setattr(self, attr, None)
        self.__updated = False

    ###
    ###   Methods dealing with the `cerebrum.entity_info' table
    ###

    def populate(self, entity_type):
        "Set instance's attributes without referring to the Cerebrum DB."
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.entity_type = entity_type

    def __xerox__(self, from_obj, reached_common=False):
        if isinstance(from_obj, Entity):
            for attr in ('entity_id', 'entity_type'):
                if hasattr(from_obj, attr):
                    setattr(self, attr, getattr(from_obj, attr))
            self.__in_db = from_obj.__in_db

    def __eq__(self, other):
        assert isinstance(other, Entity)
        identical = (self.entity_type == other.entity_type)
        if (identical and
            hasattr(self, 'entity_id') and hasattr(other, 'entity_id')):
            identical = (self.entity_id == other.entity_id)
        return identical

    def __ne__(self, other):
        """Define != (aka <>) operator as inverse of the == operator.

        Most Cerebrum classes inherit from Entity.Entity, which means
        we'll won't have to write the inverse definition of __eq__()
        over and over again."""
        return not self.__eq__(other)

    def write_db(self):
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
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.entity_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_info]
              (entity_id, entity_type)
            VALUES (:e_id, :e_type)""", {'e_id': self.entity_id,
                                         'e_type': int(self.entity_type)})
        else:
            # Don't need to do anything as entity type can't change
            pass
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def new(self, entity_type):
        """Register a new entity of ENTITY_TYPE.  Return new entity_id.

        Note that the object is not automatically associated with the
        new entity.

        """
        Entity.populate(self, entity_type)
        Entity.write_db()
        # TBD: Is this necessary?  Should it be removed, or maybe
        # exchanged with self.find()?
        Entity.find(self, self.entity_id)

    def find(self, entity_id):
        """Associate the object with the entity whose identifier is ENTITY_ID.

        If ENTITY_ID isn't an existing entity identifier,
        NotFoundError is raised.

        """
        self.entity_id, self.entity_type = self.query_1("""
        SELECT entity_id, entity_type
        FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:e_id""", {'e_id': entity_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = False

    def delete(self):
        "Completely remove an entity."
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError, \
                  "Unable to determine which entity to delete."
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self.clear()


class EntityName(object):
    "Mixin class, usable alongside Entity for entities having names."
    def get_name(self, domain):
        return self.query_1("""
        SELECT * FROM [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                          {'e_id': self.entity_id,
                           'domain': int(domain)})

    def add_name(self, domain, name):
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_name]
          (entity_id, value_domain, entity_name)
        VALUES (:e_id, :domain, :name)""", {'e_id': self.entity_id,
                                            'domain': int(domain),
                                            'name': name})

    def delete_name(self, domain):
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                            {'e_id': self.entity_id,
                             'domain': int(domain)})

    def find_by_name(self, domain, name):
        "Associate instance with the entity having NAME in DOMAIN."
        entity_id = self.query_1("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_name]
        WHERE value_domain=:domain AND entity_name=:name""",
                                 {'domain': int(domain),
                                  'name': name})
        # Populate all of self's class (and base class) attributes.
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
        INSERT INTO [:table schema=cerebrum name=entity_contact_info]
          (entity_id, source_system, contact_type, contact_pref,
           contact_value, description)
        VALUES (:e_id, :src, :type, :pref, :value, :desc)""",
                     {'e_id': self.entity_id,
                      'src': int(source),
                      'type': int(type),
                      'pref': pref,
                      'value': value,
                      'desc': description})

    def get_contact_info(self, source=None, type=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_contact_info]
            WHERE entity_id=:e_id""", {'e_id': self.entity_id}),
            ('source_system', source),
            ('contact_type', type))

    def populate_contact_info(self, type, value, contact_pref=50,
                              description=None):
        # TBD: I think this method should be deleted
        pass

    def delete_contact_info(self, source, type):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_contact_info]
        WHERE entity_id=:e_id AND source_system=:src AND
          contact_type=:c_type""",
                     {'e_id': self.entity_id,
                      'src': int(source),
                      'c_type': int(type)})


class EntityAddress(object):
    "Mixin class, usable alongside Entity for entities having addresses."

    # TBD: Does this mixin really have to keep state?  If no, it won't
    # have to use the mark_update machinery at all.  If yes, the
    # implementation should be cleaned up.
    __metaclass__ = Utils.mark_update
    __write_attr__ = ('_address_info', '_affect_source', '_affect_types')

    def clear(self):
        super(EntityAddress, self).clear()
        self._affect_source = None
        self._affect_types = None
        self._address_info = {}
        self.__updated = False

    def __eq__(self, other):
        """Note: The object that affect_addresses has been called on
        must be on the left side of the equal sign, otherwise we don't
        really know what to compare."""

        if not super(EntityAddress, self).__eq__(other):
            return False

        if self._affect_source is None:
            return True
        assert isinstance(other, EntityAddress)

        for type in self._affect_types:
            try:
                if not self._compare_addresses(type, other):
                    return False
            except KeyError, msg:
                if str(msg) == "MissingOther" and self._address_info.has_key(type):
                    return False
                return False
        return True

    def _compare_addresses(self, type, other):
        """Returns True if addresses are equal.

        Raises KeyError with msg=MissingOther/MissingSelf if the
        corresponding object doesn't have this object type.

        self must be a populated object."""
        if getattr(self, '_pn_affect_source', None) is None:
            return True
        try:
            tmp = other.get_entity_address(self._pn_affect_source, type)
            if len(tmp) == 0:
                raise KeyError
        except KeyError:
            raise KeyError, "MissingOther"
        try:
            ai = self._address_info[type]
        except KeyError:
            raise KeyError, "MissingSelf"
        for k in ('address_text', 'p_o_box', 'postal_number', 'city',
                  'country'):
            if cereconf.DEBUG_COMPARE:
                print "compare: '%s' '%s'" % (ai[k], tmp[0][k])
            if(ai[k] !=tmp[0][k]):
                return False
        return True

    def affect_addresses(self, source, *types):
        self._affect_source = source
        if types is None:
            raise NotImplementedError
        self._affect_types = types

    def populate_address(self, type, addr=None, pobox=None,
                         zip=None, city=None, country=None):
        self._address_info[type] = {'address_text': addr,
                                    'p_o_box': pobox,
                                    'postal_number': zip,
                                    'city': city,
                                    'country': country}
        pass

    def write_db(self):
        super(EntityAddress, self).write_db()
        # If affect_addresses has not been called, we don't care about
        # addresses
        if self._affect_source is None:
            return

        for type in self._affect_types:
            insert = False
            try:
                if not self._compare_addresses(type, self):
                    ai = self._address_info.get(type)
                    self.execute("""
                    UPDATE [:table schema=cerebrum name=entity_address]
                    SET address_text=:a_text, p_o_box=:p_box,
                        postal_number=:p_num, city=:city, country=:country
                    WHERE
                      entity_id=:e_id AND
                      source_system=:src AND
                      address_type=:a_type""",
                                 {'a_text': ai['address_text'],
                                  'p_box': ai['p_o_box'],
                                  'p_num': ai['postal_number'],
                                  'city': ai['city'],
                                  'country': ai['country'],
                                  'e_id': self.entity_id,
                                  'src': int(self._affect_source),
                                  'a_type': int(type)})
            except KeyError, msg:
                # Note: the arg to a python exception must be casted to str :-(
                if str(msg) == "MissingOther":
                    if self._address_info.has_key(type):
                        self.add_entity_address(self._affect_source, type,
                                                 **self._address_info[type])
                elif str(msg) == "MissingSelf":
                    delete_entity_address(self._affect_source, type)
                else:
                    raise

    def add_entity_address(self, source, type, address_text=None,
                            p_o_box=None, postal_number=None, city=None,
                            country=None):
        if cereconf.DEBUG_COMPARE:
            print "adding entity_address: %s, %s, %s, %s, %s, %s, %s, %s, " % (
                  self.entity_id, int(source), int(type), address_text,
                  p_o_box, postal_number, city, country)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_address]
          (entity_id, source_system, address_type,
           address_text, p_o_box, postal_number, city, country)
        VALUES (:e_id, :src, :a_type, :a_text, :p_box, :p_num, :city,
                :country)""",
                     {'e_id': self.entity_id,
                      'src': int(source),
                      'a_type': int(type),
                      'a_text': address_text,
                      'p_box': p_o_box,
                      'p_num': postal_number,
                      'city': city,
                      'country': country})

    def delete_entity_address(self, source_type, a_type):
        self.execute("""
                    DELETE FROM [:table schema=cerebrum name=entity_address]
                    WHERE
                      entity_id=:e_id AND
                      source_system=:src AND
                      address_type=:a_type""",
                     {'e_id': self.entity_id,
                      'src': int(source_type),
                      'a_type': int(a_type)})

    def get_entity_address(self, source=None, type=None):
        # TODO: Select * gives positional args, which is error-prone: fix

        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_address]
            WHERE entity_id=:e_id""", {'e_id': self.entity_id}),
            ('source_system', int(source)),
            ('address_type', int(type)))

    def delete_entity_address(self, source, type):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_address]
        WHERE
          entity_id=:e_id AND
          source_system=:src AND
          address_type=:a_type""", {'e_id': self.entity_id,
                                    'src': int(source),
                                    'a_type': int(type)})

class EntityQuarantine(object):
    "Mixin class, usable alongside Entity for entities we can quarantine."
    def add_entity_quarantine(self, type, creator, comment=None,
                              start=None, end=None):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_quarantine]
          (entity_id, quarantine_type,
           creator_id, comment, start_date, end_date)
        VALUES (:e_id, :q_type, :c_id, :comment, :start_date, :end_date)""",
                     {'e_id': self.entity_id,
                      'q_type': type,
                      'c_id': creator,
                      'comment': comment,
                      'start_date': start,
                      'end_date': end})

    def get_entity_quarantine(self, type=None):
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_quarantine]
            WHERE entity_id=:e_id""", {'e_id': self.entity_id}),
            ('quarantine_type', type))

    def disable_entity_quarantine(self, type, until):
        self.execute("""
        UPDATE [:table schema=cerebrum name=entity_quarantine]
        SET disable_until=:d_until
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id': self.entity_id,
                      'q_type': type,
                      'd_until': until})

    def delete_entity_quarantine(self, type):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_quarantine]
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id': self.entity_id,
                      'q_type': type})
