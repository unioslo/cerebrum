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

    __read_attr__ = ('__in_db', 'const', 'clconst',
                     # TBD: HM *thinks* these attributes should be
                     # write-once...
                     'entity_id')
    __write_attr__ = ('entity_type',)
    dontclear = ('const', 'clconst')

    def __init__(self, database):
        """

        """
        super(Entity, self).__init__(database)
        self.clear()
        self.const = Factory.get('Constants')(database)
        self.clconst = Factory.get('CLConstants')(database)

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

    def get_spread(self):
        """Return all 'spread's given to this entity."""
        return self.query("""
        SELECT spread
        FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})

    def add_spread(self, spread):
        """Add ``spread`` to this entity."""
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_spread]
          (entity_id, entity_type, spread)
        VALUES (:e_id, :e_type, :spread)""", {'e_id': self.entity_id,
                                              'e_type': int(self.entity_type),
                                              'spread': int(spread)})

    def delete_spread(self, spread):
        """Remove ``spread`` from this entity."""
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})

    def list_all_with_spread(self, spread):
        """Return sequence of all 'entity_id's that has ``spread``."""
        return self.query("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_spread]
        WHERE spread=:spread""", {'spread': spread})


class EntityName(Entity):
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

class EntityContactInfo(Entity):
    "Mixin class, usable alongside Entity for entities having contact info."

    __read_attr__ = ('_contact_info', )
    __write_attr__ = ('source_system', )

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        for attr in EntityContactInfo.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in EntityContactInfo.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False
        self._contact_info = {}

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

    def populate_contact_info(self, source_system, type=None, value=None,
                              contact_pref=50, description=None):
        if self.source_system is None:
            self.source_system = source_system
        elif self.source_system <> source_system:
            raise RuntimeError, "source_system is already set to a different value"
        if type is None:
            return
        self._contact_info[int(type)] = {'value': value,
                                         'pref': contact_pref,
                                         'description': description}

    def write_db(self):
        self.__super.write_db()
        if self.source_system is None:
            return
        for r in self.get_contact_info(source=self.source_system):
            do_del = True
            if self._contact_info.has_key(int(r['contact_type'])):
                h = self._contact_info[int(r['contact_type'])]
                print h
                if (h['value'] == r['contact_value'] and
                    h['pref'] == r['contact_pref'] and
                    h['description'] == r['description']):
                    del(self._contact_info[int(r['contact_type'])])
                    do_del = False
            if do_del:
                self.delete_contact_info(self.source_system, r['contact_type'])
        for type in self._contact_info.keys():
            self.add_contact_info(self.source_system, type,
                                  self._contact_info[type]['value'],
                                  self._contact_info[type]['pref'],
                                  self._contact_info[type]['description'])
            
    def delete_contact_info(self, source, type):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_contact_info]
        WHERE entity_id=:e_id AND source_system=:src AND
          contact_type=:c_type""",
                     {'e_id': self.entity_id,
                      'src': int(source),
                      'c_type': int(type)})


class EntityAddress(Entity):
    "Mixin class, usable alongside Entity for entities having addresses."

    # TODO: Clean this up.
    __write_attr__ = ('_address_info', '_affect_source', '_affect_types',
                      'source_system')
    __read_attr__ = ()

    def clear(self):
        super(EntityAddress, self).clear()
        self._affect_source = None
        self._affect_types = None
        self._address_info = {}
        self.__updated = False
        self.source_system = None

    # TBD:  We might decide to remove __eq__ and _compare_addresses
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

    def populate_address(self, source_system, type=None, address_text=None, p_o_box=None,
                         postal_number=None, city=None, country=None):
        if self.source_system is None:
            self.source_system = source_system
        elif self.source_system <> source_system:
            raise RuntimeError, "source_system is already set to a different value"
        if type is None:
            return
        self._address_info[int(type)] = {'address_text': address_text,
                                         'p_o_box': p_o_box,
                                         'postal_number': postal_number,
                                         'city': city,
                                         'country': country}

    def write_db(self):
        self.__super.write_db()
        if self.source_system is None:
            return
        for r in self.get_entity_address(source=self.source_system):
            do_del = True
            if self._address_info.has_key(int(r['address_type'])):
                h = self._address_info[int(r['address_type'])]
                equals = True
                for k in ('address_text', 'p_o_box', 'postal_number', 'city',
                          'country'):
                    if(h[k] != r[k]):
                        equals = False
                if equals:
                    del(self._address_info[int(r['address_type'])])
                    do_del = False
            if do_del:
                self.delete_entity_address(self.source_system, r['address_type'])

        for type in self._address_info.keys():
            self.add_entity_address(self.source_system, type,
                                  self._address_info[type]['address_text'],
                                  self._address_info[type]['p_o_box'],
                                  self._address_info[type]['postal_number'],
                                  self._address_info[type]['city'],
                                  self._address_info[type]['country'])

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
        if type is not None:
            type = int(type)
        return Utils.keep_entries(
            self.query("""
            SELECT * FROM [:table schema=cerebrum name=entity_address]
            WHERE entity_id=:e_id""", {'e_id': self.entity_id}),
            ('source_system', int(source)),
            ('address_type', type))

class EntityQuarantine(Entity):
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
