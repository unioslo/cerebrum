# Copyright 2002, 2003 University of Oslo, Norway
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
                     # Define source system once here, instead of one
                     # time per mixin class; this means that all
                     # .populate_*() calls prior to a .write_db() must
                     # use a *single* source system.
                     '_src_sys',
                     # 'entity_id' is the parent of *lots* of foreign
                     # key constraints; hence, it would probably be
                     # slightly tricky to allow this attribute to be
                     # updated.
                     #
                     # So, until someone comes up with a compelling
                     # reason for why they really need to update it,
                     # let's keep it write-once.
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

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.clear_class(Entity)
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
        # The new() method should always be overridden in subclasses.
        #
        # That way, when an object of class X has its new() method
        # called, the variable `self` in that method will always be an
        # instance of class X; it will never be an instance of a
        # subclass of X, as then that subclasses overridden new()
        # method would be the one called.
        #
        # This means that new() methods are safe in assuming that when
        # they do self.method(), the function signature of method()
        # will be the one found in the same class as new().
        self.populate(entity_type)
        self.write_db()
        self.find(self.entity_id)

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

    def list_all_with_type(self, entity_type):
        """Return sequence of all 'entity_id's that has ``type``."""
        return self.query("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_type=:entity_type""", {'entity_type': int(entity_type)})


class EntityName(Entity):
    "Mixin class, usable alongside Entity for entities having names."
    def get_name(self, domain):
        return self.query_1("""
        SELECT entity_name FROM [:table schema=cerebrum name=entity_name]
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

    def find_by_name(self, name, domain):
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

    __read_attr__ = ('__data',)

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        for attr in EntityContactInfo.__read_attr__:
            if hasattr(self, attr):
                delattr(self, attr)
        for attr in EntityContactInfo.__write_attr__:
            setattr(self, attr, None)
        self.__updated = False

    def add_contact_info(self, source, type, value, pref=None,
                         description=None):
        # TBD: Should pref=None imply use of the default pref from the
        # SQL table definition, i.e. should we avoid supplying an
        # explicit value for pref in the INSERT statement?
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
        if not hasattr(self, '_src_sys'):
            self._src_sys = source_system
        elif self._src_sys <> source_system:
            raise ValueError, \
                  "Can't populate multiple `source_system`s w/o write_db()."
        try:
            foo = self.__data
        except AttributeError:
            self.__data = {}
        if type is None:
            # No actual contact info data in this call, so only side
            # effect should be to set self.__source.
            #
            # This type of call is needed to e.g. have write_db()
            # delete all contact info associated with a particular
            # source system.
            return
        idx = "%d:%d" % (type, contact_pref)
        self.__data[idx] = {'value': value,
                            'description': description}

    def write_db(self):
        self.__super.write_db()
        if not hasattr(self, '_src_sys'):
            return
        try:
            data = self.__data
        except AttributeError:
            return
        for row in self.get_contact_info(source=self._src_sys):
            do_del = True
            row_idx = "%d:%d" % (row['contact_type'], row['contact_pref'])
            if self.__data.has_key(row_idx):
                tmp = self.__data[row_idx]
                if (tmp['value'] == row['contact_value'] and
                    tmp['description'] == row['description']):
                    del self.__data[row_idx]
                    do_del = False
            if do_del:
                self.delete_contact_info(self._src_sys,
                                         row['contact_type'],
                                         row['contact_pref'])
        for idx in self.__data.keys():
            type, pref = [int(x) for x in idx.split(":", 1)]
            self.add_contact_info(self._src_sys,
                                  type,
                                  self.__data[idx]['value'],
                                  pref,
                                  self.__data[idx]['description'])

    def delete_contact_info(self, source, type, pref='ALL'):
        sql = """
        DELETE FROM [:table schema=cerebrum name=entity_contact_info]
        WHERE
          entity_id=:e_id AND
          source_system=:src AND
          contact_type=:c_type"""
        if pref <> 'ALL':
            sql += """ AND contact_pref=:pref"""
        return self.execute(sql, {'e_id': self.entity_id,
                                  'src': int(source),
                                  'c_type': int(type),
                                  'pref': pref})


class EntityAddress(Entity):
    "Mixin class, usable alongside Entity for entities having addresses."

    __write_attr__ = ()
    __read_attr__ = ('__data',)

    def clear(self):
        super(EntityAddress, self).clear()
        self.__updated = False

    def populate_address(self, source_system, type=None,
                         address_text=None, p_o_box=None,
                         postal_number=None, city=None, country=None):
        if not hasattr(self, '_src_sys'):
            self._src_sys = source_system
        elif self._src_sys <> source_system:
            raise ValueError, \
                  "Can't populate multiple `source_system`s w/o write_db()."
        try:
            foo = self.__data
        except AttributeError:
            self.__data = {}
        if type is None:
            return
        self.__data[int(type)] = {'address_text': address_text,
                                  'p_o_box': p_o_box,
                                  'postal_number': postal_number,
                                  'city': city,
                                  'country': country}

    def write_db(self):
        self.__super.write_db()
        if not hasattr(self, '_src_sys'):
            return
        try:
            data = self.__data
        except AttributeError:
            return
        for r in self.get_entity_address(source=self._src_sys):
            do_del = True
            if self.__data.has_key(int(r['address_type'])):
                h = self.__data[int(r['address_type'])]
                equals = True
                for k in ('address_text', 'p_o_box', 'postal_number', 'city',
                          'country'):
                    if h[k] <> r[k]:
                        equals = False
                if equals:
                    del self.__data[int(r['address_type'])]
                    do_del = False
            if do_del:
                self.delete_entity_address(self._src_sys, r['address_type'])

        for type in self.__data.keys():
            self.add_entity_address(self._src_sys, type,
                                    self.__data[type]['address_text'],
                                    self.__data[type]['p_o_box'],
                                    self.__data[type]['postal_number'],
                                    self.__data[type]['city'],
                                    self.__data[type]['country'])

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
        WHERE entity_id=:e_id AND
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
