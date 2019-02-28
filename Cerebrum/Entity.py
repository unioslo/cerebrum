# -*- coding: utf-8 -*-
# Copyright 2002-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import collections

import six

import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum.Utils import argument_to_sql, prepare_string
from Cerebrum.Utils import NotSet
from Cerebrum.Utils import to_unicode


@six.python_2_unicode_compatible
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
                     'entity_id',
                     'created_at',)
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
        self.__updated = []

    #
    # Methods dealing with the `cerebrum.entity_info' table
    #

    def populate(self, entity_type):
        "Set instance's attributes without referring to the Cerebrum DB."
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
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
        """Define != operator as inverse of the == operator.

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
            self.created_at = self.query_1("""
            INSERT INTO [:table schema=cerebrum name=entity_info]
              (entity_id, entity_type)
            VALUES (:e_id, :e_type)
            RETURNING created_at""", {'e_id': self.entity_id,
                                      'e_type': int(self.entity_type)})
            self._db.log_change(self.entity_id, self.clconst.entity_add, None)
        else:
            # Don't need to do anything as entity type can't change
            pass
        del self.__in_db
        self.__in_db = True
        self.__updated = []
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

        If ENTITY_ID isn't an existing entity identifier including None,
        NotFoundError is raised.

        If ENTITY_ID input isn't an int, ValueError is raised.

        """
        if entity_id is None:
            raise Errors.NotFoundError
        self.entity_id, self.entity_type, self.created_at = self.query_1("""
        SELECT entity_id, entity_type, created_at
        FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:e_id""", {'e_id': int(entity_id)})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def delete(self):
        """Completely remove an entity."""
        if self.entity_id is None:
            raise Errors.NoEntityAssociationError(
                "Unable to determine which entity to delete.")
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self._db.log_change(self.entity_id, self.clconst.entity_del, None)
        self.clear()

    def get_delete_blockers(self, ignore_group_memberships=False, **kw):
        """Returns a list of resources blocking deletion of item.
        Not required to be exhaustive, but if empty, delete should work
        for properly constructed subclass.

        :rtype: List of strings
        :return: Every item a string representing the blocking item. Human
        readable
        """
        if ignore_group_memberships:
            return []
        import Cerebrum.Group
        # No factory, as we only want the core functionality
        gr = Cerebrum.Group.Group(self._db)
        rows = gr.search_members(member_id=self.entity_id,
                                 member_filter_expired=False)
        return ['Group {}'.format(x['group_name']) for x in rows]

    def list_all_with_type(self, entity_type):
        """Return sequence of all 'entity_id's that has ``type``."""
        return self.query("""
        SELECT entity_id
        FROM [:table schema=cerebrum name=entity_info]
        WHERE entity_type=:entity_type""", {'entity_type': int(entity_type)})

    def get_subclassed_object(self, id=None):
        """Instantiates and returns a object of the proper class
        based on the entity's type."""
        if id is not None:
            self.find(id)
        entity_type = six.text_type(self.const.EntityType(self.entity_type))
        component = Factory.type_component_map.get(entity_type)
        if component is None:
            raise ValueError("No factory for type %s" % entity_type)
        entity = Factory.get(component)(self._db)
        entity.find(self.entity_id)
        return entity

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return '{}:{}'.format(self.const.EntityType(self.entity_type),
                                  self.entity_id)
        else:
            return '<unbound entity>'


class EntitySpread(Entity):
    "Mixin class, usable alongside Entity for entities having spreads."

    def delete(self):
        """Delete an entity's spreads."""
        for s in self.get_spread():
            self.delete_spread(s['spread'])
        super(EntitySpread, self).delete()

    def get_spread(self):
        """Return all 'spread's given to this entity."""
        return self.query("""
        SELECT spread
        FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})

    def add_spread(self, spread):
        """Add ``spread`` to this entity."""
        self._db.log_change(self.entity_id, self.clconst.spread_add,
                            None, change_params={'spread': int(spread)})
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_spread]
          (entity_id, entity_type, spread)
        VALUES (:e_id, :e_type, :spread)""", {'e_id': self.entity_id,
                                              'e_type': int(self.entity_type),
                                              'spread': int(spread)})

    def delete_spread(self, spread):
        """Remove ``spread`` from this entity."""
        self._db.log_change(self.entity_id, self.clconst.spread_del,
                            None, change_params={'spread': int(spread)})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_spread]
        WHERE entity_id=:e_id AND spread=:spread""", {'e_id': self.entity_id,
                                                      'spread': int(spread)})

    def list_all_with_spread(self, spreads=None, entity_types=None):
        """Return sequence of all 'entity_id's that has ``spread``."""
        binds = dict()
        where = []
        sel = ""
        if spreads:
            where.append(argument_to_sql(spreads, 'spread', binds, int))
        if entity_types:
            where.append(argument_to_sql(entity_types, 'entity_type',
                                         binds, int))
        if where:
            sel = 'WHERE ' + ' AND '.join(where)
        return self.query("""
        SELECT entity_id, spread
        FROM [:table schema=cerebrum name=entity_spread]""" + sel, binds)

    def list_entity_spreads(self, entity_types=None):
        """Return entities and their spreads, optionally filtered by entity
        type. If entity type is None, all entities with all spreads will be
        returned.

        See also list_spreads."""
        binds = dict()
        sel = ""
        if entity_types:
            sel = """
            JOIN [:table schema=cerebrum name=entity_info] ei
              ON ei.entity_id = es.entity_id AND """
            sel += argument_to_sql(entity_types, 'ei.entity_type', binds, int)

        return self.query("""
        SELECT es.entity_id, es.spread
          FROM [:table schema=cerebrum name=entity_spread] es""" + sel, binds)

    def list_spreads(self, entity_types=None):
        """Return a sequence of spreads, optionally limited by the entity types
        the spreads are valid for.

        See also list_entity_spreads.

        @type  entity_types: EntityType constant, an int or a sequence thereof.
        @param entity_types: When not None, this parameter filters the result
            set by the entity types the spreads are valid for. When None, all
            spreads are returned."""
        binds = dict()
        where = ['(sc.entity_type = et.code)']
        if entity_types is not None:
            where.append(argument_to_sql(entity_types, "sc.entity_type", binds,
                                         int))
        return self.query("""
           SELECT sc.code as spread_code, sc.code_str as spread,
                  sc.description as description, sc.entity_type as entity_type,
                  et.code_str as entity_type_str
             FROM [:table schema=cerebrum name=spread_code] sc,
                  [:table schema=cerebrum name=entity_type_code] et
            WHERE """ + " AND ".join(where) + " ORDER BY entity_type", binds)

    def has_spread(self, spread):
        """Return true if entity has spread."""
        ent_spread = self.get_spread()
        for row in ent_spread:
            if spread in row:
                return 1
        return 0


class EntityName(Entity):
    "Mixin class, usable alongside Entity for entities having names."

    def delete(self):
        """Remove name traces of this entity from the database"""
        for n in self.get_names():
            self.delete_entity_name(n['domain_code'])
        self.__super.delete()

    def get_name(self, domain):
        return self.query_1("""
        SELECT entity_name FROM [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                            {'e_id': self.entity_id,
                             'domain': int(domain)})

    def get_names(self):
        return self.query("""
        SELECT en.entity_name AS name, en.value_domain AS domain_code
        FROM [:table schema=cerebrum name=entity_name] en
        WHERE en.entity_id=:e_id""",
                          {'e_id': self.entity_id})

    def add_entity_name(self, domain, name):
        self._db.log_change(self.entity_id, self.clconst.entity_name_add, None,
                            change_params={'domain': int(domain),
                                           'name': name})
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_name]
          (entity_id, value_domain, entity_name)
        VALUES (:e_id, :domain, :name)""", {'e_id': self.entity_id,
                                            'domain': int(domain),
                                            'name': name})

    def delete_entity_name(self, domain):
        self._db.log_change(self.entity_id, self.clconst.entity_name_del, None,
                            change_params={'domain': int(domain),
                                           'name': self.get_name(int(domain))})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                            {'e_id': self.entity_id,
                             'domain': int(domain)})

    def update_entity_name(self, domain, name):
        if int(domain) in [int(self.const.ValueDomain(code_str))
                           for code_str in
                           cereconf.NAME_DOMAINS_THAT_DENY_CHANGE]:
            raise self._db.IntegrityError(
                "Name change illegal for the domain: %s" % domain)
        self.execute("""
        UPDATE [:table schema=cerebrum name=entity_name]
        SET entity_name=:name
        WHERE entity_id=:e_id AND value_domain=:domain""",
                     {'e_id': self.entity_id,
                      'domain': int(domain),
                      'name': name})
        self._db.log_change(self.entity_id, self.clconst.entity_name_mod, None,
                            change_params={'domain': int(domain),
                                           'name': name})

    def find_by_name(self, name, domain):
        "Associate instance with the entity having NAME in DOMAIN."
        if not isinstance(name, basestring):
            raise ValueError("invalid name {name!r}".format(name=name))

        entity_id = self.query_1(
            """
            SELECT entity_id
            FROM [:table schema=cerebrum name=entity_name]
            WHERE value_domain=:domain AND entity_name=:name
            """,
            {
                'domain': int(domain),
                'name': six.text_type(name),
            }
        )
        # Populate all of self's class (and base class) attributes.
        self.find(entity_id)

    def list_names(self, value_domain):
        return self.query(
            """
            SELECT entity_id, value_domain, entity_name
            FROM [:table schema=cerebrum name=entity_name]
            WHERE value_domain=:value_domain
            """,
            {'value_domain': int(value_domain)})


class EntityNameWithLanguage(Entity):
    """Mixin class for dealing with name-with-language data in Cerebrum.

    This mixin adds support for adorning entities with (potentially) non-unique
    names. Each entity may have up to one name of a specific type in a given
    language.
    """

    def _query_builder(self, entity_id, name_variant, name_language, name,
                       exact_match=True, include_where=True):
        """Help build the WHERE-part of SQL-queries for this class.

        exact_match decides whether the name matching is to be exact or
        approximate (with LIKE). In the latter case we do NOT allow multiple
        values for name (there are no current use cases for this and this
        extension is complex enough as it is). Furthermore, exact_match's value
        is meaningless, unless name is not None.

        Additionally, if exact_match is False we'll prefix/suffix name with '%'
        (if it does not contain them already).

        @return:
          A tuple <query, binds>, where query is a str containing the SQL and
          binds is a dict with free variables (if any) referenced by
          query. include_where controls whether query is prefixed with
          'WHERE '.
        """

        binds = {}
        where = list()
        if entity_id is not None:
            where.append(
                argument_to_sql(
                    entity_id,
                    "eln.entity_id",
                    binds,
                    int))
        if name_variant is not None:
            where.append(
                argument_to_sql(name_variant, "eln.name_variant", binds,
                                int))
        if name_language is not None:
            where.append(
                argument_to_sql(name_language, "eln.name_language", binds,
                                int))
        if name is not None:
            if exact_match:
                where.append(argument_to_sql(name, "eln.name", binds,
                                             six.text_type))
            else:
                name_pattern = prepare_string(name)
                if name_pattern.count('%') == 0:
                    name_pattern = '%' + name_pattern + '%'
                where.append("(LOWER(eln.name) LIKE :name)")
                binds["name"] = name_pattern

        where = " AND ".join(where) or ""
        if include_where and where:
            where = " WHERE " + where

        return where, binds

    def add_name_with_language(self, name_variant, name_language, name):
        """Add or update a specific language name."""

        binds = {"name_variant": int(name_variant),
                 "name_language": int(name_language),
                 "name": name,
                 "entity_id": self.entity_id}
        change_params = {'name_variant': int(name_variant),
                         'name_language':
                         int(self.const.LanguageCode(name_language)),
                         'name': name}
        existing = self.search_name_with_language(entity_id=self.entity_id,
                                                  name_variant=name_variant,
                                                  name_language=name_language)
        if existing:
            # If the names are equal, stop now and do NOT flood the change log.
            m = existing[0]
            if to_unicode(m["name"], "latin-1") == to_unicode(name, "latin-1"):
                return

            rv = self.execute("""
            UPDATE [:table schema=cerebrum name=entity_language_name]
            SET name = :name
            WHERE entity_id = :entity_id AND
                  name_variant = :name_variant AND
                  name_language = :name_language
            """, binds)
            self._db.log_change(
                self.entity_id, self.clconst.entity_name_mod, None,
                change_params=change_params)
        else:
            rv = self.execute("""
            INSERT INTO [:table schema=cerebrum name=entity_language_name]
            VALUES (:entity_id, :name_variant, :name_language, :name)
            """, binds)
            self._db.log_change(
                self.entity_id, self.clconst.entity_name_add, None,
                change_params=change_params)
            return rv

    def delete_name_with_language(self, name_variant=None, name_language=None,
                                  name=None):
        """Delete specific language name entries for self.

        With all filters left unset, this will delete all of self's language
        names.
        """

        where, binds = self._query_builder(self.entity_id, name_variant,
                                           name_language, name)

        # Why bother? Well, because IF the specified name does not exist, we do
        # NOT want to flood the logs. Imagine 20'000 entities with name
        # data. Imagine a bunch of deletion calls from an outdated
        # source which results in deletion of names which no longer exist (and
        # have not existed for a while). Unless we catch that here, the
        # change_log will be slapped with 20'000x<#name types>x<#langs>
        # superfluous entries per run. This cannot be allowed.
        existing = self.search_name_with_language(entity_id=self.entity_id,
                                                  name_variant=name_variant,
                                                  name_language=name_language,
                                                  name=name)
        rv = self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_language_name] eln
        """ + where, binds)

        if existing:
            # Why not a specific constant? Well, because
            # name_variant/name_language/name could all be a sequence or an
            # iterable. It should work regardless.
            change_params = {'name_variant': six.text_type(name_variant),
                             'name_language': six.text_type(name_language),
                             'name': name}
            self._db.log_change(self.entity_id, self.clconst.entity_name_del,
                                None, change_params=change_params)
        return rv

    def delete(self):
        """Remove all known names for self from the database."""

        # We could use search_name_with_language() +
        # delete_name_with_language(), but that combo cannot be made atomic
        # without extra effort. Is it worth the effort, just to get
        # changelogging?
        where, binds = self._query_builder(self.entity_id, None, None, None)
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_language_name] eln
        """ + where, binds)
        return self.__super.delete()

    def search_name_with_language(self, entity_id=None, entity_type=None,
                                  name_variant=None, name_language=None,
                                  name=None, exact_match=True):
        """Look for language name entries matching specified filters.

        Without filters, return all names with languages for everything.

        @type entity_id: int or list of int
        @param entity_id: If set, only the names of the given entities are
            returned.

        @type entity_type: CerebrumConstant, int or list of such
        @param entity_type: If set, only the names for the given entity types
            are returned.

        @type name_variant: CerebrumConstant, int or list of such
        @param name_variant: Filter result by given name types, like full name,
            given name and/or family name.

        @type name_language: CerebrumConstant, int or list of such
        @param name_language: Filter result by given languages.

        @type name: string
        @param name: Filter by given name. Could contain wildcards, like % or
        ?. The character * gets swapped out with %. Note that L{exact_match}
        affects this string.

        @type exact_match: bool
        @param exact_match:
            Controls whether name matching is to be exact (foo = 'bar') or
            approximate (foo LIKE '%bar%'). In the latter case, if name has no
            SQL-wildcards, they will be supplied automatically.

        @rtype: db-rows
        @return: Each row contains the element L{entity_id}, L{entity_type},
            L{name_variant}, L{name_language}, L{name}.
        """
        where = ["ei.entity_id = eln.entity_id", ]
        where2, binds = self._query_builder(entity_id, name_variant,
                                            name_language, name, exact_match,
                                            include_where=False)
        if where2:
            where.append(where2)
        if entity_type is not None:
            where.append(
                argument_to_sql(
                    entity_type,
                    "ei.entity_type",
                    binds,
                    int))

        return self.query("""
        SELECT eln.entity_id, ei.entity_type,
               eln.name_variant, eln.name_language, eln.name
        FROM [:table schema=cerebrum name=entity_language_name] eln,
             [:table schema=cerebrum name=entity_info] ei
        WHERE """ + " AND ".join(where), binds)

    def get_name_with_language(
            self, name_variant, name_language, default=NotSet):
        """Retrieve a specific name for self.

        A short-hand for search_name_with_language + raise NotFoundError
        """

        names = self.search_name_with_language(entity_id=self.entity_id,
                                               name_variant=name_variant,
                                               name_language=name_language)
        if len(names) == 1:
            return names[0]["name"]
        elif default != NotSet:
            return default
        elif not names:
            raise Errors.NotFoundError(
                "Entity id=%s has no name %s in lang=%s" %
                (self.entity_id,
                 self.const.EntityNameCode(name_variant),
                 self.const.LanguageCode(name_language)))
        elif len(names) > 1:
            raise Errors.TooManyRowsError(
                "Too many rows id=%s (%s, %s): %d" %
                (self.entity_id,
                 self.const.EntityNameCode(name_variant),
                 self.const.LanguageCode(name_language),
                 len(names)))
        assert False, "NOTREACHED"


class EntityContactInfo(Entity):
    "Mixin class, usable alongside Entity for entities having contact info."

    __read_attr__ = ('__data',)

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        self.clear_class(EntityContactInfo)
        self.__updated = []

    def delete(self):
        """Delete all contact info for this entity"""
        for r in self.get_contact_info():
            self.delete_contact_info(r['source_system'], r['contact_type'])
        self.__super.delete()

    def add_contact_info(self, source, type, value, pref=None,
                         description=None, alias=None):
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
           contact_value, description, contact_alias)
        VALUES (:e_id, :src, :type, :pref, :value, :desc, :alias)""",
                     {'e_id': self.entity_id,
                      'src': int(source),
                      'type': int(type),
                      'pref': pref,
                      'value': value,
                      'desc': description,
                      'alias': alias})
        self._db.log_change(self.entity_id, self.clconst.entity_cinfo_add,
                            None,
                            change_params={'type': int(type),
                                           'value': value,
                                           'src': int(source)})

    def get_contact_info(self, source=None, type=None):
        where = []
        binds = {}
        where.append(argument_to_sql(self.entity_id, 'entity_id', binds, int))
        if source is not None:
            where.append(argument_to_sql(source, 'source_system', binds, int))
        if type is not None:
            where.append(argument_to_sql(type, 'contact_type', binds, int))
        where_str = 'WHERE ' + ' AND '.join(where)

        return self.query("""
            SELECT *
            FROM [:table schema=cerebrum name=entity_contact_info]
            %s
            ORDER BY contact_pref""" % (where_str), binds)

    def populate_contact_info(self, source_system, type=None, value=None,
                              contact_pref=50, description=None, alias=None):
        if not hasattr(self, '_src_sys'):
            self._src_sys = source_system
        elif self._src_sys != source_system:
            raise ValueError("Can't populate multiple `source_system`s "
                             "w/o write_db().")
        try:
            self.__data
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
        # For some contact values, e.g. phone numbers, it makes sense
        # to pass in numeric 'value' arguments.  However, this breaks
        # the update magic in write_db(), as the values it compares
        # against are fetched from a text column in the database.
        #
        # To avoid such problems, the 'value' argument is always
        # converted to a string before being stored in self.__data.
        self.__data[idx] = {'value': six.text_type(value),
                            'alias': alias and six.text_type(alias) or None,
                            'description': description}

    def write_db(self):
        self.__super.write_db()
        if not hasattr(self, '_src_sys'):
            return
        try:
            data = self.__data.copy()
        except AttributeError:
            return
        for row in self.get_contact_info(source=self._src_sys):
            do_del = True
            row_idx = "%d:%d" % (row['contact_type'], row['contact_pref'])
            if row_idx in data:
                tmp = data[row_idx]
                if (tmp['value'] == row['contact_value'] and
                    tmp['alias'] == row['contact_alias'] and
                        tmp['description'] == row['description']):
                    del data[row_idx]
                    do_del = False
            if do_del:
                self.delete_contact_info(self._src_sys,
                                         row['contact_type'],
                                         # FIXME: Workaround for
                                         # stupid PgSQL bug; any
                                         # PgNumeric with value zero
                                         # is treated as NULL.
                                         int(row['contact_pref']))
        for idx in data:
            type, pref = [int(x) for x in idx.split(":", 1)]
            self.add_contact_info(self._src_sys,
                                  type,
                                  data[idx]['value'],
                                  pref,
                                  data[idx]['description'],
                                  data[idx]['alias'])
    # end write_db

    def delete_contact_info(self, source, contact_type, pref='ALL'):
        if not self.get_contact_info(source, contact_type):
            # Nothing to delete
            return
        sql = """
        DELETE FROM [:table schema=cerebrum name=entity_contact_info]
        WHERE
          entity_id=:e_id AND
          source_system=:src AND
          contact_type=:c_type"""
        if six.text_type(pref) != 'ALL':
            sql += """ AND contact_pref=:pref"""
        self._db.log_change(self.entity_id, self.clconst.entity_cinfo_del,
                            None,
                            change_params={'type': int(contact_type),
                                           'src': int(source)})
        return self.execute(sql, {'e_id': self.entity_id,
                                  'src': int(source),
                                  'c_type': int(contact_type),
                                  'pref': pref})
    # end delete_contact_info

    def list_contact_info(self, entity_id=None, source_system=None,
                          contact_type=None, entity_type=None,
                          contact_value=None, contact_alias=None):
        """List entity contact information, constrained by specific filters.

        Without any filters, this method will return the content of the entire
        entity_contact_info table.

        @type entity_id: None or (int or a sequence thereof).
        @param entity_id:
          Contact info 'holders' (entities for which contact data is sought)

        @type source_system:
          None or (int/AuthoritativeSystem or a sequence thereof).
        @param source_system:
          Filter contact information by source system.

        @type contact_type: None or (int/ContactInfo or a sequence thereof)
        @param contact_type:
          Filter contact information by contact type (fax, phone, e-mail,
          etc.)

        @type entity_type: None or (int/EntityType or a sequence thereof)
        @param entity_type:
          Filter contact information by owning entity's type (i.e. all
          persons' contact info, rather than OUs')
        """

        binds = dict()
        where = list()
        for name, transform in (("entity_id", int),
                                ("source_system", int),
                                ("contact_type", int),
                                ("contact_value", six.text_type),
                                ("contact_alias", six.text_type)):
            if locals()[name] is not None:
                where.append(argument_to_sql(locals()[name],
                                             "ec." + name,
                                             binds,
                                             transform))
        where = " AND ".join(where)
        join = ""
        if entity_type is not None:
            chunk = argument_to_sql(entity_type, "e.entity_type", binds, int)
            join = """
            JOIN [:table schema=cerebrum name=entity_info] e
              ON ec.entity_id = e.entity_id AND
            """ + chunk

        if where:
            where = "WHERE " + where

        return self.query("""
        SELECT ec.*
        FROM  [:table schema=cerebrum name=entity_contact_info] ec
        %s   /* inner join with entity_info, if any */
        %s   /* where clause, if any */
        ORDER BY ec.entity_id, ec.contact_pref""" % (join, where), binds)
    # end list_contact_info

    @staticmethod
    def sort_contact_info(spec, contacts):
        """Sort an entitys contact info according to a specification.

            The following specification:
                [(system_fs, mobile),
                 (system_sap, home),
                 (system_fs, None),
                 (None, mobile),
                 (None, None)]
            Will order mobile numbers from FS before home numbers from SAP.
            Then it will prefer all contact values from FS, before prefering
            all mobile numbers from other systems. None is in this context
            a wildcard. The (None, None) tuple matches all source systems
            and contact types.

            If a source_system and contact_type combination is not matched by
            the specification, it will be filtered out from the sorted results.

        :param spec: A list of tuples defining the specification contacts
            should be sorted according to. The tuple members type must be
            subclassed from CerebrumCode or NoneType.
        :param contacts: A list of db_row objects representing contacts.
        :return: A list of db_row objects sorted according to spec.
        """
        from functools import total_ordering

        # Term for elements that should be dropped
        @total_ordering
        class Exclude(object):
            def __lt__(self, other):
                return True

            def __eq__(self, other):
                return (self is other)

        # Utility function for resolving order according to spec
        def order_to_spec(spec, e):
            key = (e['source_system'], e['contact_type'])
            if key in spec:
                return spec.index(key)

            (s, t) = key
            if (s, None) in spec:
                return spec.index((s, None))
            elif (None, t) in spec:
                return spec.index((None, t))
            elif (None, None) in spec:
                return spec.index((None, None))
            else:
                return Exclude()

        from operator import itemgetter
        from functools import partial

        # Sort by preference before sorting by spec
        pref_sorted = sorted(contacts, key=itemgetter('contact_pref'))
        spec_sorted = sorted(pref_sorted, key=partial(order_to_spec, spec))

        # Filter out elements that are not defined in the spec
        return filter(
            lambda e: not isinstance(order_to_spec(spec, e), Exclude),
            spec_sorted)


class EntityAddress(Entity):

    "Mixin class, usable alongside Entity for entities having addresses."

    __write_attr__ = ()
    __read_attr__ = ('__data',)

    def clear(self):
        super(EntityAddress, self).clear()
        self.__updated = []
        self.clear_class(EntityAddress)

    def delete(self):
        """Delete all address info for this entity"""
        for r in self.get_entity_address():
            self.delete_entity_address(r['source_system'], r['address_type'])
        self.__super.delete()

    def populate_address(self, source_system, type=None,
                         address_text=None, p_o_box=None,
                         postal_number=None, city=None, country=None):
        if not hasattr(self, '_src_sys'):
            self._src_sys = source_system
        elif self._src_sys != source_system:
            raise ValueError(
                "Can't populate multiple `source_system`s w/o write_db().")
        try:
            self.__data
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
            data = self.__data.copy()
        except AttributeError:
            return
        for r in self.get_entity_address(source=self._src_sys):
            do_del = True
            if int(r['address_type']) in data:
                h = data[int(r['address_type'])]
                equals = True
                for k in ('address_text', 'p_o_box', 'postal_number', 'city',
                          'country'):
                    if h[k] != r[k]:
                        equals = False
                if equals:
                    del data[int(r['address_type'])]
                    do_del = False
            if do_del:
                self.delete_entity_address(self._src_sys, r['address_type'])

        for type in data.keys():
            self.add_entity_address(self._src_sys, type,
                                    data[type]['address_text'],
                                    data[type]['p_o_box'],
                                    data[type]['postal_number'],
                                    data[type]['city'],
                                    data[type]['country'])

    def add_entity_address(self, source, type, address_text=None,
                           p_o_box=None, postal_number=None, city=None,
                           country=None):
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
        self._db.log_change(self.entity_id, self.clconst.entity_addr_add, None)

    def delete_entity_address(self, source_type, a_type):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_address]
        WHERE entity_id=:e_id AND
              source_system=:src AND
              address_type=:a_type""",
                     {'e_id': self.entity_id,
                      'src': int(source_type),
                      'a_type': int(a_type)})
        self._db.log_change(self.entity_id, self.clconst.entity_addr_del, None)

    def get_entity_address(self, source=None, type=None):
        cols = {'entity_id': int(self.entity_id)}
        if source is not None:
            cols['source_system'] = int(source)
        if type is not None:
            cols['address_type'] = int(type)
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=entity_address]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                   for x in cols.keys()]), cols)

    def list_country_codes(self):
        return self.query("""
            SELECT * FROM [:table schema=cerebrum name=country_code]""")

    def list_entity_addresses(self, entity_type=None, source_system=None,
                              address_type=None, entity_id=None):
        binds = dict()
        where = list()

        e_type = ""
        if entity_type is not None:
            e_type = """
            JOIN [:table schema=cerebrum name=entity_info] e
              ON e.entity_id = ea.entity_id AND """
            e_type += argument_to_sql(entity_type, 'e.entity_type', binds, int)

        if source_system is not None:
            where.append(argument_to_sql(source_system, 'ea.source_system',
                                         binds, int))
        if address_type is not None:
            where.append(argument_to_sql(address_type, 'ea.address_type',
                                         binds,
                                         int))
        if entity_id is not None:
            where.append(argument_to_sql(entity_id, 'ea.entity_id', binds,
                                         int))

        where_str = ''
        if where:
            where_str = 'WHERE ' + ' AND '.join(where)

        return self.query("""
        SELECT ea.entity_id, ea.source_system, ea.address_type,
               ea.address_text, ea.p_o_box, ea.postal_number, ea.city,
               ea.country
        FROM [:table schema=cerebrum name=entity_address] ea
        %s %s""" % (e_type, where_str), binds)


class EntityQuarantine(Entity):
    "Mixin class, usable alongside Entity for entities we can quarantine."

    def delete(self):
        """Delete all quarantines for this entity"""
        for r in self.get_entity_quarantine():
            self.delete_entity_quarantine(r['quarantine_type'])
        self.__super.delete()

    def add_entity_quarantine(self,
                              qtype,
                              creator,
                              description=None,
                              start=None,
                              end=None):
        """
        Add quarantine for this entity
        """
        qtype = int(qtype)
        self.execute(
            """ INSERT INTO [:table schema=cerebrum name=entity_quarantine]
            (entity_id, quarantine_type, creator_id, description,
             start_date, end_date)
            VALUES
            (:entity_id, :quarantine_type, :creator_id, :description,
             :start_date, :end_date)
            """,
            {'entity_id': self.entity_id,
             'quarantine_type': qtype,
             'creator_id': creator,
             'description': description,
             'start_date': start,
             'end_date': end})

        self._db.log_change(self.entity_id,
                            self.clconst.quarantine_add,
                            None,
                            change_params={'q_type': qtype,
                                           'start': start,
                                           'end': end, })

    def get_entity_quarantine(self,
                              qtype=None,
                              only_active=False,
                              ignore_disable_until=False,
                              filter_disable_until=False):
        """Return a list of the current entity's quarantines.

        :type qtype: CerebrumConstant or int
        :param qtype: If set, only quarantines of the given type is returned.

        :type only_active: bool
        :param only_active: If True, only return quarantines with a start_date
            in the past and a not set or future end_date.
            In addition, disable_until must be in the past if set.

        :type ignore_disable_until: bool
        :param ignore_disable_until: If True, disabled_until is ignored when
            considering whether quarantines are active.

        :type filter_disable_until: bool
        :param filter_disable_until: If True, only quarantines with
            disable_until not set or its date in the past will be returned.
            only_active must be False for this argument to have any impact.
        """
        conditions = ["entity_id = :e_id"]
        if only_active:
            conditions += [
                "start_date <= [:now]",
                "(end_date IS NULL OR end_date > [:now])"]
        if (only_active and not ignore_disable_until) or filter_disable_until:
            conditions += [
                "(disable_until IS NULL OR disable_until <= [:now])"]
        if qtype is not None:
            conditions += ["quarantine_type = :qtype"]
            qtype = int(qtype)
        return self.query("""
            SELECT quarantine_type, creator_id, description,
                create_date, start_date, disable_until, end_date
            FROM [:table schema=cerebrum name=entity_quarantine]
            WHERE """ + " AND ".join(conditions),
                          {'e_id': self.entity_id,
                           'qtype': qtype})

    def disable_entity_quarantine(self, qtype, until):
        """Disable a quarantine for the current entity until a specified time.

        :type qtype: QuarantineCode or int
        :param qype: The quarantine to be disabled

        :type until: mx.DateTime
        :param until: Disable quarantine until this point in time
        """
        self.execute("""
        UPDATE [:table schema=cerebrum name=entity_quarantine]
        SET disable_until=:d_until
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id': self.entity_id,
                      'q_type': int(qtype),
                      'd_until': until})
        self._db.log_change(self.entity_id, self.clconst.quarantine_mod,
                            None, change_params={'q_type': int(qtype)})

    def delete_entity_quarantine(self, qtype):
        """Delete a quarantine for the current entity.

        :type qtype: QuarantineCode or int
        :param qype: The quarantine to be deleted

        :rtype: bool
        :returns: Was a quarantine deleted?
        """
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_quarantine]
        WHERE entity_id=:e_id AND quarantine_type=:q_type""",
                     {'e_id': self.entity_id,
                      'q_type': int(qtype)})
        if self._db.rowcount:
            self._db.log_change(self.entity_id, self.clconst.quarantine_del,
                                None, change_params={'q_type': int(qtype)})
            return True
        return False

    def list_entity_quarantines(self, entity_types=None, quarantine_types=None,
                                only_active=False, entity_ids=None,
                                ignore_quarantine_types=None, spreads=None):
        sel = ""
        where = ""
        binds = dict()
        conditions = []
        if entity_types:
            sel = """
            JOIN [:table schema=cerebrum name=entity_info] ei
              ON ei.entity_id = eq.entity_id AND """
            sel += argument_to_sql(entity_types, "ei.entity_type", binds, int)
        # argument_to_sql doesn't handle same value in binds twice, e.g.
        # quarantine_type
        if quarantine_types and ignore_quarantine_types:
            raise Errors.CerebrumError(
                "Can't use both quarantine_types and ignore_quarantine_types")
        if quarantine_types:
            conditions.append(
                argument_to_sql(quarantine_types, "quarantine_type",
                                binds, int))
        if ignore_quarantine_types:
            conditions.append(
                "NOT " + argument_to_sql(
                    ignore_quarantine_types, "quarantine_type", binds, int))
        if only_active:
            conditions.append("""start_date <= [:now] AND
            (end_date IS NULL OR end_date > [:now]) AND
            (disable_until IS NULL OR disable_until <= [:now])""")
        if entity_ids:
            conditions.append(
                argument_to_sql(entity_ids, "eq.entity_id", binds, int))
        if spreads:
            sel += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON es.entity_id = ei.entity_id AND """
            sel += argument_to_sql(spreads, "es.spread", binds, int)
        if conditions:
            where = " WHERE " + " AND ".join(conditions)
        return self.query("""
        SELECT eq.entity_id, eq.quarantine_type, eq.start_date,
               eq.disable_until, eq.end_date, eq.description
          FROM [:table schema=cerebrum name=entity_quarantine] eq""" +
                          sel + where, binds)


class EntityExternalId(Entity):
    "Mixin class, usable alongside Entity for ExternalIds."
    __read_attr__ = ('_extid_source', '_extid_types')
    __write_attr__ = ()

    def clear(self):
        self.__super.clear()
        self._external_id = {}
        self.clear_class(EntityExternalId)
        self.__updated = []

    def delete(self):
        # Entities cannot be both Persons and OUs with the same entity_id
        # so not joining on entity_type should be safe.
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_external_id]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def write_db(self):
        self.__super.write_db()

        if hasattr(self, '_extid_source'):
            dbvalues = {}
            for row in self.get_external_id(source_system=self._extid_source):
                dbvalues[row['id_type']] = six.text_type(row['external_id'])
            for type in self._extid_types:
                val = self._external_id.get(type)
                dbval = dbvalues.get(type)
                if val is not None:
                    val = six.text_type(val)
                if val != dbval:
                    if val is None:
                        self._delete_external_id(self._extid_source, type)
                    elif dbval is None:
                        self._set_external_id(self._extid_source, type, val)
                    else:
                        self._set_external_id(
                            self._extid_source,
                            type,
                            val,
                            update=True)

    def affect_external_id(self, source, *types):
        self._extid_source = source
        self._extid_types = [int(x) for x in types]

    def populate_external_id(self, source_system, id_type, external_id):
        if not hasattr(self, '_extid_source'):
            raise ValueError("Must call affect_external_id")
        elif self._extid_source != source_system:
            raise ValueError(
                "Can't populate multiple `source_system`s w/o write_db().")
        self._external_id[int(id_type)] = external_id

    def _delete_external_id(self, source_system, id_type):
        self.execute("""DELETE FROM [:table schema=cerebrum name=entity_external_id]
        WHERE entity_id=:p_id AND id_type=:id_type AND source_system=:src""",
                     {'p_id': self.entity_id,
                      'id_type': int(id_type),
                      'src': int(source_system)})
        self._db.log_change(self.entity_id, self.clconst.entity_ext_id_del,
                            None,
                            change_params={'id_type': int(id_type),
                                           'src': int(source_system)})

    def _set_external_id(self, source_system, id_type, external_id,
                         update=False):
        if update:
            sql = """UPDATE [:table schema=cerebrum name=entity_external_id]
            SET external_id=:ext_id
            WHERE entity_id=:e_id AND id_type=:id_type AND source_system=:src
            """
            self._db.log_change(
                self.entity_id, self.clconst.entity_ext_id_mod, None,
                change_params={'id_type': int(id_type),
                               'src': int(source_system),
                               'value': external_id})
        else:
            sql = """
            INSERT INTO [:table schema=cerebrum name=entity_external_id]
            (entity_id, entity_type, id_type, source_system, external_id)
            VALUES (:e_id, :e_type, :id_type, :src, :ext_id)"""
            self._db.log_change(
                self.entity_id, self.clconst.entity_ext_id_add, None,
                change_params={'id_type': int(id_type),
                               'src': int(source_system),
                               'value': external_id})
        self.execute(sql, {'e_id': self.entity_id,
                           'e_type': int(self.entity_type),
                           'id_type': int(id_type),
                           'src': int(source_system),
                           'ext_id': external_id})

    def get_external_id(self, source_system=None, id_type=None):
        binds = dict()
        where = list()

        where.append(argument_to_sql(self.entity_id, 'entity_id', binds, int))
        where.append(argument_to_sql(self.entity_type, 'entity_type', binds,
                                     int))
        if source_system is not None:
            where.append(argument_to_sql(source_system, "source_system", binds,
                                         int))
        if id_type is not None:
            where.append(argument_to_sql(id_type, "id_type", binds, int))

        where_str = 'WHERE %s' % ' AND '.join(where)

        return self.query("""
        SELECT id_type, source_system, external_id
        FROM [:table schema=cerebrum name=entity_external_id]
        %s
        """ % where_str, binds)

    def search_external_ids(self, source_system=None, id_type=None,
                            external_id=None, entity_type=None,
                            entity_id=None, fetchall=True):
        """Search for external IDs matching specified criteria.

        @type source_system: int or AuthoritativeSystemCode or sequence thereof
        @param source_system:
            Filter resulting IDs by given source system(s).

        @type id_type: int or EntityExternalId or sequence thereof
        @param id_type:
            Filter resulting IDs by ID type(s).

        @type external_id: basestring
        @param external_id:
            Filter resulting IDs by external ID, case insensitively. The ID may
            contain SQL wildcard characters. Useful for finding the entity a
            given external ID belongs to.

        @type entity_type: int or EntityType or sequence thereof
        @param entity_type:
            Filter resulting IDs by entity type. Note that external IDs are
            already limited by entity_type - you can only set a given id type
            for a certain entity type.

        @type entity_id: int or sequence therof
        @param entity_id:
            Filter resulting IDs by given entitites. Useful for looking up
            (all) external ids belonging to a specific entity).

        @type fetchall: bool
        @param fetchall:
            Fetch all results or return a generator object with the results.

        @rtype: iterable (yielding db-rows)
        @return:
            An iterable (sequence or a generator) that yields all db-rows that
            matches the given criterias. The values of each db-row are:
            entity_id, entity_type, id_type, source_system, external_id.

        """
        binds = dict()
        where = list()
        if source_system is not None:
            where.append(argument_to_sql(source_system, "source_system", binds,
                                         int))
        if id_type is not None:
            where.append(argument_to_sql(id_type, "id_type", binds, int))
        if entity_type is not None:
            where.append(argument_to_sql(entity_type, "entity_type", binds,
                                         int))
        if entity_id is not None:
            where.append(argument_to_sql(entity_id, "entity_id", binds, int))
        if external_id is not None:
            external_id = prepare_string(external_id)
            where.append("(LOWER(external_id) LIKE :external_id)")
            binds['external_id'] = external_id

        where_str = ''
        if where:
            where_str = 'WHERE %s' % ' AND '.join(where)
        return self.query("""
            SELECT entity_id, entity_type, id_type, source_system, external_id
            FROM [:table schema=cerebrum name=entity_external_id]
            %s""" % where_str, binds, fetchall=fetchall)
        # TODO: might want to look at setting fetchall, but need to figure out
        # what the ups and downs are. Speed versus memory?

    # The following method will have the argument "entity_type"
    # removed. The reason is that entity_type can be found in
    # id_type. To do this a lot of code has to be looked into.
    def find_by_external_id(self, id_type, external_id, source_system=None,
                            entity_type=None):
        binds = {'id_type': int(id_type),
                 'ext_id': external_id,
                 'entity_type': int(id_type.entity_type)}
        where = ""
        if source_system is not None:
            binds['src'] = int(source_system)
            where = " AND source_system=:src"
        entity_id = self.query_1("""
        SELECT DISTINCT entity_id
        FROM [:table schema=cerebrum name=entity_external_id]
        WHERE id_type=:id_type AND external_id=:ext_id AND
        entity_type=:entity_type %s""" % where, binds)
        self.find(entity_id)

    def find_by_external_ids(self, *ids):
        """Lookup entity by external ID's.

        If the ID's given resolve to one unique person, i.e.:
        * This person has one or more of these unique ID's, and
        * No other person has a matching ID, then
        self is bound to this particular entity.

        :param ids: Each ID should either be a tuple where the first element
                    denotes an id_type, and the second should be an
                    external_id. The tuple can also have a third element being
                    the source system.
                    Else, the id could be a dict with keys 'id_type',
                    'external_id', and 'source_system' (optional). The
                    meaning of each element in ids matches arguments to
                    find_by_external_id().
        :returns: Result of self.find()
        :raises: TooManyRowsError if more than one person matches, or a
                 NotFoundError if no person matches.
        """
        # TODO: Is it better to create a long WHERE clause combined with OR?
        query = """
        SELECT DISTINCT entity_id
        FROM [:table schema=cerebrum name=entity_external_id]
        WHERE id_type=:id_type AND external_id=:ext_id AND
        entity_type=:entity_type"""

        def make_bind(id_type, external_id, source_system=None):
            ret = {'id_type': int(id_type),
                   'ext_id': external_id,
                   'entity_type': int(id_type.entity_type)}
            if source_system:
                ret['src'] = int(source_system)
            return ret

        def make_bind_str(id_type, external_id, source_system=None):
            ret = {'id_type': six.text_type(id_type),
                   'ext_id': external_id,
                   'src': None}
            if source_system:
                ret['src'] = six.text_type(source_system)
            return "(id_type:{id_type} id:{ext_id} source:{src})".format(**ret)

        opt_ss = query + " AND source_system=:src"

        found = []
        found_ids = set()
        for i in ids:
            bind = (make_bind(**i) if isinstance(i, collections.Mapping)
                    else make_bind(*i))
            bindstr = (make_bind_str(**i) if isinstance(i, collections.Mapping)
                       else make_bind_str(*i))
            q = query if 'src' not in bind else opt_ss
            rows = self.query(q, bind)
            if len(rows) > 1:
                raise Errors.TooManyRowsError(
                    "External id {} returned too many ({}) rows".format(
                        bindstr, len(rows)))
            if rows:
                found.append((bindstr, rows[0]['entity_id']))
                found_ids.add(rows[0]['entity_id'])
        if len(found_ids) == 1:
            return self.find(*found_ids)
        if len(found_ids) > 1:
            strs = ["bind:{} matches id:{}".format(i, j) for i, j in found]
            raise Errors.TooManyRowsError("More than one entity found: " +
                                          ", ".join(strs))
        raise Errors.NotFoundError("No entity found matching given ids")

    def _set_cached_external_id(self, variant, value):
        sys_cache = self.const.system_cached
        try:
            old_value = self.get_external_id(sys_cache, variant)
            if value is None:
                self._delete_external_id(sys_cache, variant)
            elif old_value != value:
                self._set_external_id(sys_cache, variant, value, update=True)
        except Errors.NotFoundError:
            if value is not None:
                self._set_external_id(sys_cache, variant, value)
