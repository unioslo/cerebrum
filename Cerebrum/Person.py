# -*- coding: utf-8 -*-
#
# Copyright 2002-2020 University of Oslo, Norway
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
Base class for Cerebrum person objects.
"""
from __future__ import unicode_literals

import collections
import numbers

import six

import cereconf
from Cerebrum.Entity import (EntityContactInfo,
                             EntityAddress,
                             EntityQuarantine,
                             EntityExternalId,
                             EntitySpread,
                             EntityNameWithLanguage)
from Cerebrum import Utils
from Cerebrum.Utils import argument_to_sql, prepare_string
from Cerebrum import Errors


class MissingOtherException(Exception):
    pass


class MissingSelfException(Exception):
    pass


Entity_class = Utils.Factory.get("Entity")


@six.python_2_unicode_compatible
class Person(EntityContactInfo, EntityExternalId, EntityAddress,
             EntityQuarantine, EntitySpread, EntityNameWithLanguage,
             Entity_class):
    __read_attr__ = ('__in_db', '_affil_source', '__affil_data')
    __write_attr__ = ('birth_date', 'gender', 'description', 'deceased_date')

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        self.clear_class(Person)
        self.__updated = []

        # TODO: The following attributes are currently not in
        #       Person.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        # Person names:
        self._pn_affect_source = None
        self._pn_affect_variants = None
        self._name_info = {}

    def delete(self):
        """ Actually delete the entity. """
        # Remove person from person_name, person_affiliation,
        # person_affiliation_source, person_info. Super will remove
        # the entity from the mix-in classes
        for r in self.get_names():
            self._delete_name(r['source_system'], r['name_variant'])
        for r in self.get_affiliations(include_deleted=True):
            self.nuke_affiliation(r['ou_id'], r['affiliation'],
                                  r['source_system'], r['status'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_info]
        WHERE person_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def populate(
        self, birth_date, gender, description=None, deceased_date=None,
            parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_person)
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
        self.birth_date = birth_date
        self.gender = gender
        self.description = description
        self.deceased_date = deceased_date

    def __eq__(self, other):
        """Define == operator for Person objects."""
        assert isinstance(other, Person)
        identical = self.__super.__eq__(other)
        if not identical:
            return False

        if not identical:
            return False

        if self._pn_affect_source is not None:
            for type in self._pn_affect_variants:
                other_name = other.get_name(self._pn_affect_source, type)
                my_name = self._name_info.get(type, None)
                if my_name != other_name:
                    identical = False
                    break
        if not identical:
            return False

        identical = ((other.birth_date == self.birth_date) and
                     (other.gender == int(self.gender)) and
                     (other.description == self.description) and
                     (other.deceased_date == self.deceased_date))
        return identical

    def write_db(self):
        """ Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        :returns: Some convoluted logic that is supposed to indicate what has
                  changed.

        """
        self.__super.write_db()
        if self.__updated:
            is_new = not self.__in_db
            if is_new:
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=person_info]
                  (entity_type, person_id, export_id, birth_date, gender,
                   deceased_date, description)
                VALUES
                  (:e_type, :p_id, :exp_id, :b_date, :gender,
                   :deceased_date, :desc)""",
                             {'e_type': int(self.const.entity_person),
                              'p_id': self.entity_id,
                              'exp_id': 'exp-' + six.text_type(self.entity_id),
                              'b_date': self.birth_date,
                              'gender': int(self.gender),
                              'deceased_date': self.deceased_date,
                              'desc': self.description})
                self._db.log_change(
                    self.entity_id,
                    self.clconst.person_create,
                    None)
            else:
                binds = {'export_id': 'exp-' + six.text_type(self.entity_id),
                         'birth_date': self.birth_date,
                         'gender': int(self.gender),
                         'deceased_date': self.deceased_date,
                         'description': self.description,
                         'person_id': self.entity_id}
                exists_stmt = """
                  SELECT EXISTS (
                    SELECT 1
                    FROM [:table schema=cerebrum name=person_info]
                    WHERE (export_id is NULL AND :export_id is NULL OR
                             export_id=:export_id) AND
                          (birth_date is NULL AND :birth_date is NULL OR
                             birth_date=:birth_date) AND
                          (deceased_date is NULL AND :deceased_date is NULL OR
                             deceased_date=:deceased_date) AND
                          (description is NULL AND :description is NULL OR
                             description=:description) AND
                         gender=:gender AND
                         person_id=:person_id
                  )
                """
                if not self.query_1(exists_stmt, binds):
                    # True positive
                    update_stmt = """
                    UPDATE [:table schema=cerebrum name=person_info]
                    SET export_id=:export_id,
                        birth_date=:birth_date,
                        gender=:gender,
                        deceased_date=:deceased_date,
                        description=:description
                    WHERE person_id=:person_id"""
                    self.execute(update_stmt, binds)
                    self._db.log_change(self.entity_id,
                                        self.clconst.person_update,
                                        None)
        else:
            is_new = None

        # Handle PersonAffiliations
        if hasattr(self, '_affil_source'):
            source = self._affil_source
            # db_affil is used to see if the exact affiliation exists
            # (or did exist earlier, and is marked as deleted)
            db_affil = {}
            # db_prim is used to see if a row with that primary key
            # exists.
            db_prim = {}
            for row in self.get_affiliations(include_deleted=True):
                if source == row['source_system']:
                    idx = "%d:%d:%d" % (
                        row['ou_id'],
                        row['affiliation'],
                        row['status'])
                    db_affil[idx] = row['deleted_date']
                    db_prim['%s:%s' % (row['ou_id'], row['affiliation'])] = idx
            pop_affil = self.__affil_data
            for prim in pop_affil.keys():
                status, precedence = pop_affil[prim]
                idx = "%s:%d" % (prim, status)
                if idx in db_affil:
                    # This affiliation, including status, exists in the
                    # database already:
                    #   - If deleted: resurrect
                    #   - If not deleted: Update last_date.
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.add_affiliation(ou_id, affil, source,
                                         status, precedence)
                    del db_affil[idx]
                else:
                    # This may be a completely new affiliation, or just a
                    # change in status.
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.add_affiliation(ou_id, affil, source,
                                         status, precedence)
                    if is_new != 1:
                        is_new = False
                    if prim in db_prim:
                        # it was only a change of status.  make sure
                        # the loop below won't delete the affiliation.
                        del db_affil[db_prim[prim]]
            # Delete all the remaining affiliations. Some of them are already
            # marked as deleted.
            for idx in db_affil.keys():
                if db_affil[idx] is None:
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.delete_affiliation(ou_id, affil, source)
                    if is_new != 1:
                        is_new = False
            delattr(self, '_affil_source')
            delattr(self, '_Person__affil_data')

        # If affect_names has not been called, we don't care about
        # names
        if self._pn_affect_source is not None:
            updated_name = False
            for variant in self._pn_affect_variants:
                try:
                    if not self._compare_names(variant, self):
                        self._update_name(
                            self._pn_affect_source,
                            variant,
                            self._name_info[variant])
                        is_new = False
                        updated_name = True
                except MissingOtherException:
                    if variant in self._name_info:
                        self._set_name(self._pn_affect_source, variant,
                                       self._name_info[variant])
                        if is_new != 1:
                            is_new = False
                        updated_name = True
                except MissingSelfException:
                    self._delete_name(self._pn_affect_source, variant)
                    is_new = False
                    updated_name = True
            if updated_name:
                self._update_cached_names()
            # Clear affect_name() settings
            self._pn_affect_source = None
            self._pn_affect_variants = None
            self._name_info = {}

        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def new(self, birth_date, gender, description=None, deceased_date=None):
        """Register a new person."""
        self.populate(birth_date, gender, description, deceased_date)
        self.write_db()
        self.find(self.entity_id)

    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        self.__super.find(person_id)
        (self.export_id, self.birth_date, self.gender,
         self.deceased_date, self.description) = self.query_1(
             """SELECT export_id, birth_date, gender,
                      deceased_date, description
               FROM [:table schema=cerebrum name=person_info]
               WHERE person_id=:p_id""", {'p_id': person_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    # FIXME: these find_* functions should be renamed list_*
    def find_persons_by_bdate(self, bdate):
        return self.query("""
        SELECT person_id FROM [:table schema=cerebrum name=person_info]
        WHERE birth_date = :bdate""", locals())

    def find_by_export_id(self, export_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        WHERE export_id=:export_id""", locals())
        self.find(person_id)

    def _compare_names(self, variant, other):
        """Returns True if names are equal.

        self must be a populated object."""

        try:
            tmp = other.get_name(self._pn_affect_source, variant)
        except Exception:
            raise MissingOtherException
        try:
            myname = self._name_info[variant]
        except Exception:
            raise MissingSelfException
        return tmp == myname

    def _set_name(self, source_system, variant, name):
        # Class-internal use only
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=person_name]
          (person_id, name_variant, source_system, name)
        VALUES (:p_id, :n_variant, :src, :name)""",
                     {'p_id': self.entity_id,
                      'n_variant': int(variant),
                      'src': int(source_system),
                      'name': name})
        self._db.log_change(self.entity_id, self.clconst.person_name_add, None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _delete_name(self, source, variant):
        binds = {'person_id': self.entity_id,
                 'source_system': int(source),
                 'name_variant': int(variant)}
        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=person_name]
          WHERE person_id=:person_id AND
                source_system=:source_system AND
                name_variant=:name_variant
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=person_name]
        WHERE person_id=:person_id AND
              source_system=:source_system AND
              name_variant=:name_variant
        """
        self.execute(delete_stmt, binds)
        self._db.log_change(self.entity_id,
                            self.clconst.person_name_del, None,
                            change_params={'src': int(source),
                                           'name_variant': int(variant)})

    def _update_name(self, source_system, variant, name):
        # Class-internal use only
        binds = {'name': name,
                 'person_id': self.entity_id,
                 'source_system': int(source_system),
                 'name_variant': int(variant)}
        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=person_name]
          WHERE person_id=:person_id AND
                source_system=:source_system AND
                name_variant=:name_variant AND
                name=:name
          )
        """
        if self.query_1(exists_stmt, binds):
            # False positive
            return
        update_stmt = """
          UPDATE [:table schema=cerebrum name=person_name]
          SET name=:name
          WHERE person_id=:person_id AND
                source_system=:source_system AND
                name_variant=:name_variant
        """
        self.execute(update_stmt, binds)
        self._db.log_change(self.entity_id,
                            self.clconst.person_name_mod,
                            None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _set_cached_name(self, variant, name):
        sys_cache = self.const.system_cached
        try:
            old_name = self.get_name(sys_cache, variant)
            if name is None:
                self._delete_name(sys_cache, variant)
            elif old_name != name:
                self._update_name(sys_cache, variant, name)
        except Errors.NotFoundError:
            if name is not None:
                self._set_name(sys_cache, variant, name)

    def _update_cached_names(self):
        """Update cache of person's names.

        The algorithm for constructing the cached name values looks
        for the first source system in cereconf.SYSTEM_LOOKUP_ORDER
        with enough data to construct a full name for the person.

        Once a full name has been established (either an actual
        registered full name or a source system in which both first
        and last name is registered), the search through the source
        systems continues until a first and last name pair matching
        the full name is found.

        If no such first and last name pair is found, split the full
        name to guess at those name variants.

        Persons with no first name _must_ be registered with an
        explicit first name of "": a single-word full name is not
        trusted.

        A ValueError is raised if no cacheworthy name variants are
        found for the person."""

        # The keys in this dict tells us which name variants should be
        # kept in the cache.  The corresponding values will be set as
        # we walk through the name data from the authoritative source
        # systems.
        cached_name = {
            'name_first': None,
            'name_last': None,
            'name_full': None
        }
        for ss in cereconf.SYSTEM_LOOKUP_ORDER:
            source = getattr(self.const, ss)
            names = {}
            for ntype in cached_name.keys():
                try:
                    names[ntype] = self.get_name(source,
                                                 getattr(self.const, ntype))
                except Errors.NotFoundError:
                    continue
            if not names:
                # This source system had no name data on this person.
                continue
            gen_full = None
            if 'name_first' in names and 'name_last' in names:
                if names['name_first'] == '':
                    gen_full = names['name_last']
                else:
                    gen_full = names['name_first'] + ' ' + names['name_last']
            if cached_name['name_full'] is None:
                if 'name_full' in names:
                    cached_name['name_full'] = names['name_full']
                elif gen_full:
                    cached_name['name_full'] = gen_full
                else:
                    # None of the source systems this far have
                    # presented us with enough data to form a full
                    # name.
                    continue
            # Here, we know that cached_name['name_full'] is set to
            # the person's proper full name; if gen_full is set, we
            # know the current source system has good values for first
            # and last name, too.
            if gen_full == cached_name['name_full']:
                cached_name['name_first'] = names['name_first']
                cached_name['name_last'] = names['name_last']
            if None not in cached_name.values():
                # All name variants in cached_name are present; we're
                # ready to start updating the database.
                break
        else:
            # Couldn't find proper data for caching of all name
            # variants.  If there is cacheable data for full name, our
            # last, best hope for getting cached first- and last names
            # is to chop the full name apart.
            if cached_name['name_full'] is not None:
                name_parts = cached_name['name_full'].split()
                if len(name_parts) >= 2:
                    last_name = name_parts.pop()
                    if cached_name['name_last'] is None:
                        cached_name['name_last'] = last_name
                    if cached_name['name_first'] is None:
                        cached_name['name_first'] = " ".join(name_parts)

        # Update the cache if a name is found in a system referred to by
        # cereconf.SYSTEM_LOOKUP_ORDER
        if [n for n in cached_name if cached_name[n] is not None]:
            for ntype, name in cached_name.items():
                name_type = getattr(self.const, ntype)
                self._set_cached_name(name_type, name)

    def list_person_name_codes(self):
        return self.query(
            """
              SELECT code, description
              FROM [:table schema=cerebrum name=person_name_code]
            """)

    def list_person_affiliation_codes(self):
        return self.query(
            """
              SELECT code, code_str, description
              FROM [:table schema=cerebrum name=person_affiliation_code]
            """)

    def get_name(self, source_system, variant):
        """Return the name with the given variant"""
        return self.query_1(
            """
              SELECT name
              FROM [:table schema=cerebrum name=person_name]
              WHERE
                person_id=:p_id AND
                name_variant=:n_variant AND
                source_system=:src
            """,
            {
                'p_id': self.entity_id,
                'n_variant': int(variant),
                'src': int(source_system),
            })

    def get_names(self, source_system=None, variant=None):
        """Return all names connected to this person,
        optionally filtered on source_system or variant.
        """
        binds = dict(person_id=int(self.entity_id))
        where = 'WHERE person_id = :person_id'

        if source_system is not None:
            where += ' AND ' + argument_to_sql(source_system, 'source_system',
                                               binds, int)
        if variant is not None:
            where += ' AND ' + argument_to_sql(variant, 'name_variant',
                                               binds, int)

        return self.query(
            """
              SELECT *
              FROM [:table schema=cerebrum name=person_name]
            """ + where,
            binds)

    def affect_names(self, source, *variants):
        self._pn_affect_source = source
        if variants is None:
            raise NotImplementedError
        self._pn_affect_variants = variants

    def populate_name(self, variant, name):
        if (not self._pn_affect_source or
            six.text_type(variant) not in ["%s" % v
                                           for v in self._pn_affect_variants]):
            raise ValueError("Improper API usage, must call affect_names()")
        self._name_info[variant] = name

    def populate_affiliation(self, source_system, ou_id=None,
                             affiliation=None, status=None, precedence=None):
        if not hasattr(self, '_affil_source'):
            self._affil_source = source_system
            self.__affil_data = {}
        elif self._affil_source != source_system:
            raise ValueError(
                "Can't populate multiple `source_system`s w/o write_db().")
        if ou_id is None:
            return
        idx = "%d:%d" % (ou_id, affiliation)
        self.__affil_data[idx] = int(status), precedence

    def get_affiliations(self, include_deleted=False):
        return self.list_affiliations(self.entity_id,
                                      include_deleted=include_deleted)

    # exchange-relatert-jazz
    # create an easy way to populate automatic groups with
    # primary account_id rather then person_id
    def list_affiliations(self, person_id=None, source_system=None,
                          affiliation=None, status=None, ou_id=None,
                          include_deleted=False, ret_primary_acc=False,
                          fetchall=True):
        """Retrieve a list of affiliations matching criteria. Retrieves
        rows from person_affiliation_source.

        :type person_id: NoneType or int
        :param person_id: Only matching this person. Also, sort result
            by precedence (unless ret_primary_acc).

        :type source_system: NoneType, int or AuthoritativeSystem code
        :param source_system: Filter by source system

        :type affiliation: NoneType, int or PersonAffiliation code
        :param affiliation: Only this kind of affiliation

        :type status: NoneType, int or PersonAffStatus code
        :param status: Filter by affiliation status

        :type ou_id: NoneType or int
        :param ou_id: Filter by ou (not recursive)

        :type include_deleted: bool
        :param include_deleted: If false, filter out deleted affs,
            i.e. deleted_date in past.

        :type ret_primary_acc: bool
        :param ret_primary_acc: Hack to make person_id become account_id.

        :type fetchall: bool
        :param fetchall: Fetch all rows?

        :returns: List of dbrows:
            * person_id
            * ou_id
            * affiliation
            * source_system
            * status
            * deleted_date
            * create_date
            * last_date
            * precedence
        """
        where = []
        for t in ('person_id', 'affiliation', 'source_system', 'status',
                  'ou_id'):
            val = locals()[t]
            if val is not None:
                if isinstance(val, (list, tuple, set)):
                    where.append("pas.%s IN (%s)" %
                                 (t, ", ".join(map(
                                     six.text_type, map(int, val)))))
                else:
                    where.append("pas.%s = %d" % (t, val))
        if not include_deleted:
            where.append("(pas.deleted_date IS NULL OR "
                         "pas.deleted_date > [:now])")
        where = " AND ".join(where)
        if where:
            where = "WHERE " + where
        order = ""
        if person_id is not None:
            order = "ORDER BY precedence ASC"
        # exchange-relatert-jazz
        # this is a bit dirty as the return values are registered as
        # "person_id" while they actually are account_id's
        # it is however the quickest way of solving the requirement
        # of creating auto-groups populated by primary accounts
        # (Jazz, 2013-12)
        if ret_primary_acc:
            return self.query("""
            SELECT
              ai.account_id AS person_id,
              pas.ou_id AS ou_id,
              pas.affiliation AS affiliation,
              pas.source_system AS source_system, pas.status AS status,
              pas.deleted_date AS deleted_date,
              pas.create_date AS create_date,
              pas.last_date AS last_date,
              pas.precedence AS precedence
            FROM [:table schema=cerebrum name=person_affiliation_source] pas,
                 [:table schema=cerebrum name=account_info] ai,
                 [:table schema=cerebrum name=account_type] at
            %s AND
            ai.owner_id=pas.person_id AND
            at.account_id=ai.account_id AND
            at.priority = (SELECT min(at2.priority)
                           FROM
                            [:table schema=cerebrum name=account_type] at2,
                            [:table schema=cerebrum name=account_info] ai2
                           WHERE
                               at2.person_id = pas.person_id AND
                               at2.account_id = ai2.account_id AND
                               (ai2.expire_date IS NULL OR
                                ai2.expire_date > [:now]))
            """ % where, fetchall=fetchall)
        return self.query("""
        SELECT
              pas.person_id AS person_id,
              pas.ou_id AS ou_id,
              pas.affiliation AS affiliation,
              pas.source_system AS source_system, pas.status AS status,
              pas.deleted_date AS deleted_date,
              pas.create_date AS create_date,
              pas.last_date AS last_date,
              pas.precedence AS precedence
        FROM [:table schema=cerebrum name=person_affiliation_source] pas
        {} {}
        """.format(where, order), fetchall=fetchall)

    def __get_affiliation_precedence_rule(self, source,
                                          afforrule, status=None):
        """ Helper for aff calculation """
        def search(rule, first, *rest):
            if not isinstance(rule, dict):
                # We have found our goal
                return rule
            if not rest:
                if first in rule:
                    return rule[first]
                return rule.get('*')
            if first in rule:
                res = search(rule[first], *rest)
                if res is not None:
                    return res
            if '*' in rule:
                return search(rule['*'], *rest)
            return None

        source = six.text_type(self.const.AuthoritativeSystem(source))
        if not isinstance(afforrule, six.string_types):
            afforrule = six.text_type(self.const.PersonAffiliation(afforrule))
        args = [cereconf.PERSON_AFFILIATION_PRECEDENCE_RULE, source, afforrule]
        if status is not None:
            if not isinstance(status, six.string_types):
                status = self.const.PersonAffStatus(status).str
            args.append(status)
        return search(*args)

    def __calculate_affiliation_precedence(self, affiliation, source,
                                           status, precedence, old):
        """ Helper for add_affiliation """
        if precedence is None:
            if old:
                return old
            precedence = self.__get_affiliation_precedence_rule(source,
                                                                affiliation,
                                                                status)
            return self.__calculate_affiliation_precedence(affiliation,
                                                           source, status,
                                                           precedence, old)
        if isinstance(precedence, numbers.Integral):
            return precedence
        if isinstance(precedence, six.string_types):
            precedence = self.__get_affiliation_precedence_rule(source,
                                                                precedence)
            return self.__calculate_affiliation_precedence(affiliation,
                                                           source, status,
                                                           precedence, old)
        # Assume some sequence
        assert (isinstance(precedence, collections.Sequence) and
                len(precedence) in (2, 3))
        if isinstance(precedence[0], six.string_types):
            precedence = self.__get_affiliation_precedence_rule(
                source, *precedence)
            return self.__calculate_affiliation_precedence(affiliation,
                                                           source, status,
                                                           precedence, old)
        # We should now have a range, (min, max)
        mn, mx = precedence[:2]  # special case of single value
        if mn == mx:
            return mn
        if old:
            # Old is in correct range, change nothing
            if mn <= old < mx:
                return old

            # If there is an override range, use old if inside
            override = cereconf.PERSON_AFFILIATION_PRECEDENCE_RULE.get(
                'core:override')
            if override and override[0] <= old < override[1]:
                return old

        # No old, find new spot
        all_precs = set((x['precedence'] for x in
                         self.get_affiliations(include_deleted=True)))
        x = max([mn] + [x for x in all_precs if mn <= x < mx])
        step = 5
        if len(precedence) > 2:
            step = precedence[2]
        while x in all_precs:
            x += step
        return x

    def __clear_precedence(self, precedence, all_precs):
        """ Clear precedences. """
        row = all_precs[precedence]
        if precedence + 1 in all_precs:
            self.__clear_precedence(precedence + 1, all_precs)

        keys = "person_id ou_id affiliation source_system".split()
        binds = dict((x for x in row.items() if x[0] in keys))
        binds['precedence'] = precedence + 1
        self.execute(
            """
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET precedence = :precedence
            WHERE person_id = :person_id AND
                  ou_id = :ou_id AND
                  affiliation = :affiliation AND
                  source_system = :source_system""", binds)

    def add_affiliation(self,
                        ou_id,
                        affiliation,
                        source,
                        status,
                        precedence=None):
        """Add or update affiliation.

        :type ou_id: OU object or int
        :param ou_id: Specifies an OU for this aff.

        :type affiliation: PersonAffiliation code or int
        :param affiliation: An affiliation code.

        :type source: AuthoritativeSystem code or int
        :param source: Source system

        :type status: PersonAffStatus code or int
        :param status: Affiliation status

        :type precedence: int, sequence or NoneType
        :param precedence:
            Precedence is a number, and affiliations are sorted by preference
            (lowest to highest).
            :None:
                The current precedence is kept, or a precedence is calculated
                using cereconf.PERSON_AFFILIATION_PRECEDENCE_RULE (PAPR).
            :int:
                Updates the precedence to given number. If not available,
                will lower precedence for colliding affiliations. (i.e.
                having affs [a(1), b(2), c(3)], adding d(2) makes
                [a(1), d(2), b(3), c(4)].
            :string or sequence of strings:
                Works as with None, but will look for string in PAPR:
                * "foo" → PAPR[str(source)][precedence]
                * ["foo", "bar"] →
                  PAPR[str(source)][precedence[0]][precedence[1]]
            If a matching precedence rule is not found in PAPR, a more general
            rule will be selected.
        """

        all_prs = dict()
        for row in self.list_affiliations(person_id=self.entity_id,
                                          include_deleted=True):
            all_prs[int(row['precedence'])] = row
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'status': int(status),
                 'p_id': self.entity_id,
                 }
        updprec = ", precedence=:precedence"
        if not isinstance(affiliation, self.const.PersonAffiliation):
            affiliation = self.const.PersonAffiliation(int(affiliation))
        if not isinstance(status, self.const.PersonAffStatus):
            status = self.const.PersonAffStatus(int(status))
        if not isinstance(source, self.const.AuthoritativeSystem):
            source = self.const.AuthoritativeSystem(int(source))
        change_params = {
            'ou_id': int(ou_id),
            'affiliation': int(affiliation),
            'affiliationstr': six.text_type(affiliation),
            'source': int(source),
            'sourcestr': six.text_type(source),
            'status': int(status),
            'statusstr': six.text_type(status)
        }
        # If needed, add to table 'person_affiliation'.
        try:
            self.query_1("""
            SELECT 'yes' AS yes
            FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", binds)
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation]
              (person_id, ou_id, affiliation)
            VALUES (:p_id, :ou_id, :affiliation)""", binds)
            self._db.log_change(
                self.entity_id,
                self.clconst.person_aff_add, None,
                change_params={
                    'ou_id': int(ou_id),
                    'affiliation': int(affiliation),
                    'affiliationstr': six.text_type(affiliation)
                })
        try:
            cur_status, cur_precedence, cur_del = self.query_1("""
            SELECT status, precedence, deleted_date
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            cur_status, cur_precedence = int(cur_status), int(cur_precedence)

            new_prec = self.__calculate_affiliation_precedence(affiliation,
                                                               source, status,
                                                               precedence,
                                                               cur_precedence)
            binds['precedence'] = new_prec
            if new_prec in all_prs and new_prec != cur_precedence:
                self.__clear_precedence(new_prec, all_prs)
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET status=:status, last_date=[:now], deleted_date=NULL {}
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""".format(updprec), binds)
            if cur_del:
                self._db.log_change(self.entity_id,
                                    self.clconst.person_aff_src_add, None,
                                    change_params=change_params)
                return 'add', status, precedence
            if cur_status != int(status) or cur_precedence != new_prec:
                cur_status = self.const.PersonAffStatus(cur_status)
                change_params['oldstatus'] = int(cur_status)
                change_params['oldstatusstr'] = six.text_type(cur_status)
                self._db.log_change(self.entity_id,
                                    self.clconst.person_aff_src_mod, None,
                                    change_params=change_params)
                return 'mod', cur_status, cur_precedence
        except Errors.NotFoundError:
            pr = binds['precedence'] = self.__calculate_affiliation_precedence(
                affiliation, source, status, precedence, None)
            if pr in all_prs:
                self.__clear_precedence(pr, all_prs)
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation_source]
             (person_id, ou_id, affiliation, source_system, status, precedence)
            VALUES (:p_id, :ou_id, :affiliation, :source, :status, :precedence)
            """,
                         binds)
            self._db.log_change(self.entity_id,
                                self.clconst.person_aff_src_add, None,
                                change_params=change_params)
            return 'add', status, precedence
        return False, status, precedence

    def delete_affiliation(self, ou_id, affiliation, source):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'p_id': self.entity_id,
                 }
        if not isinstance(affiliation, self.const.PersonAffiliation):
            affiliation = self.const.PersonAffiliation(int(affiliation))
        if not isinstance(source, self.const.AuthoritativeSystem):
            source = self.const.AuthoritativeSystem(int(source))

        status = self.query_1(
            """
            SELECT status
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE person_id=:p_id AND
                  ou_id=:ou_id AND
                  affiliation=:affiliation AND
                  source_system=:source""", binds)
        change_params = {
            'ou_id': int(ou_id),
            'affiliation': int(affiliation),
            'affiliationstr': six.text_type(affiliation),
            'source': int(source),
            'sourcestr': six.text_type(source),
            'status': int(status),
            'statusstr': six.text_type(self.const.PersonAffStatus(status))
        }
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_affiliation_source]
        SET deleted_date=[:now]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", binds)
        self._db.log_change(self.entity_id,
                            self.clconst.person_aff_src_del, None,
                            change_params=change_params)
        # This method doesn't touch table 'person_affiliation', nor
        # does it try to do any actual deletion of rows from table
        # 'person_affiliation_source'; these tasks are in the domain
        # of various database cleanup procedures.

    def nuke_affiliation(self, ou_id, affiliation, source, status):
        p_id = self.entity_id
        # This method shouldn't be used lightly; see
        # .delete_affiliation().
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", locals())
        if not isinstance(affiliation, self.const.PersonAffiliation):
            affiliation = self.const.PersonAffiliation(affiliation)
        if not isinstance(status, self.const.PersonAffStatus):
            status = self.const.PersonAffStatus(status)
        if not isinstance(source, self.const.AuthoritativeSystem):
            source = self.const.AuthoritativeSystem(source)
        change_params = {
            'ou_id': int(ou_id),
            'affiliation': int(affiliation),
            'affiliationstr': six.text_type(affiliation),
            'source': int(source),
            'sourcestr': six.text_type(source),
            'status': int(status),
            'statusstr': six.text_type(status)
        }
        self._db.log_change(self.entity_id,
                            self.clconst.person_aff_src_del, None,
                            change_params=change_params)
        remaining_affiliations = self.query("""
        SELECT 'yes' AS yes
        FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation""", locals())
        if not remaining_affiliations:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", locals())
            self._db.log_change(
                self.entity_id,
                self.clconst.person_aff_del, None,
                change_params={
                    'ou_id': int(ou_id),
                    'affiliation': int(affiliation),
                    'affiliationstr': six.text_type(affiliation)
                })

    # Will remove all entries in person_affiliation_source for a given
    # source system. Typically to clean up authorative sources no longer
    # in use, such as Ureg.
    def nuke_affiliation_for_source_system(self, source_system):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE source_system=%s""" % source_system)
        if not isinstance(source_system, self.const.AuthoritativeSystem):
            source_system = self.const.AuthoritativeSystem(source_system)
        self._db.log_change(self.entity_id,
                            self.clconst.person_aff_src_del, None,
                            change_params={
                                'source': int(source_system),
                                'sourcestr': six.text_type(source_system)
                            })

    def get_accounts(self, filter_expired=True):
        acc = Utils.Factory.get('Account')(self._db)
        return acc.list_accounts_by_owner_id(self.entity_id,
                                             filter_expired=filter_expired)

    def get_primary_account(self):
        """Returns the account_id of SELF.entity_id's primary account"""
        acc = Utils.Factory.get("Account")(self._db)
        # get_account_types returns its results sorted
        accounts = acc.get_account_types(all_persons_types=True,
                                         owner_id=self.entity_id)
        if accounts:
            return accounts[0]["account_id"]
        return None

    def getdict_external_id2primary_account(self, id_type):
        """
        Returns a dictionary mapping all existing external ids of given
        ID_TYPE to the corresponding primary account.

        This is a *convenience* function. The very same thing can be
        accomplished with get_primary_account() + Account.find() and a
        suitable number of database lookups
        """

        result = dict()

        # NB! outer joins are not necessary here. Not displaying FNRs with
        # missing accounts is quite alright.
        # Loosely speaking -- we select a non-expired account having the
        # smallest priority among the non-expired accounts.
        for row in self.query("""
            SELECT
              DISTINCT eei.external_id, en.entity_name
            FROM
              [:table schema=cerebrum name=entity_external_id] eei,
              [:table schema=cerebrum name=account_type] at,
              [:table schema=cerebrum name=entity_name] en
            WHERE
              -- make sure the external id is of the right kind
              eei.id_type = :id_type AND
              -- ... and it applies to a person
              eei.entity_type = [:get_constant name=entity_person] AND
              -- ... and the external id belongs to the account owner
              eei.entity_id = at.person_id AND
              -- ... and the priority is the smallest among non-expired
              -- ... accounts for the same person
              at.priority = (SELECT
                               min(at2.priority)
                             FROM
                               [:table schema=cerebrum name=account_type] at2,
                               [:table schema=cerebrum name=account_info] ai2
                             WHERE
                               at2.person_id = eei.entity_id AND
                               at2.account_id = ai2.account_id AND
                               (ai2.expire_date IS NULL OR
                                ai2.expire_date > [:now])) AND
              -- ... and finally to find the name of the account
              at.account_id = en.entity_id
                              """, {"id_type": int(id_type)}):
            result[row["external_id"]] = row["entity_name"]

        return result

    def list_affiliated_persons(self,
                                aff_list=None,
                                status_list=None,
                                inverted=False):
        """
        Retrieve a list of all persons with the specified affiliations
        and / or statuses

        :type aff_list: NoneType, int or list
        :param aff_list: If not None only persons having one or more of the
                         listed affiliations will be listed

        :type status_list: NoneType, int or list
        :param status_list: If not None only persons having one or more of the
                            listed statuses will be listed

        :type inverted: bool
        :param inverted: Reverse the query and list only persons that do *not*
                        posess the specified affiliations and statuses.
                        Default: False
        """
        binds = dict()
        where = ('WHERE pi.person_id = pas.person_id '
                 'AND (deleted_date IS NULL OR deleted_date > CURRENT_DATE)')
        if aff_list is not None:
            where += ' AND ' + argument_to_sql(aff_list,
                                               'pas.affiliation',
                                               binds,
                                               int,
                                               inverted)
        if status_list is not None:
            where += ' AND ' + argument_to_sql(status_list,
                                               'pas.status',
                                               binds,
                                               int,
                                               inverted)
        # where += " LIMIT 100"
        q = """
        SELECT DISTINCT pi.person_id AS person_id, pi.birth_date AS birth_date
        FROM [:table schema=cerebrum name=person_info] pi,
             [:table schema=cerebrum name=person_affiliation_source] pas
        """ + where
        # print('DEBUG: ' + q)
        return self.query(q, binds)

    def list_persons(self, person_id=None):
        """Return all persons' person_id and birth_date."""
        binds = dict()
        where = ''
        if person_id is not None:
            where = 'WHERE ' + argument_to_sql(person_id, 'person_id',
                                               binds, int)
        return self.query("""
        SELECT person_id, birth_date
        FROM [:table schema=cerebrum name=person_info]
        """ + where, binds)

    def getdict_persons_names(self, source_system=None, name_types=None):
        if name_types is None:
            name_types = self.const.name_full
        if isinstance(name_types, (list, tuple)):
            selection = "IN (%s)" % ", ".join(
                map(six.text_type, map(int, name_types)))
        else:
            selection = "= %d" % int(name_types)
        if source_system is not None:
            selection += " AND source_system = %d" % int(source_system)
        result = {}
        for id, variant, name in self.query("""
        SELECT DISTINCT person_id, name_variant, name
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % selection):
            id = int(id)
            info = result.get(id)
            if info is None:
                result[id] = {int(variant): name}
            else:
                info[int(variant)] = name
        return result

    def list_persons_atype_extid(
            self, spread=None, include_quarantines=False, idtype=None):
        """Multiple join to increase performance on LDAP-dump.

        TBD: Maybe this should be nuked in favor of pure dumps like
             list_persons."""
        efrom = ecols = ""
        if include_quarantines:
            efrom = """
            LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
              ON at.account_id=eq.entity_id"""
            ecols = ", eq.quarantine_type"
        if spread is not None:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON pi.person_id=es.entity_id AND es.spread=:spread"""
        if idtype:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_external_id] eei
            ON pi.person_id = eei.entity_id AND eei.id_type=:idtype AND
               eei.entity_type = [:get_constant name=entity_person]"""
        else:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_external_id] eei
            ON pi.person_id = eei.entity_id AND
               eei.entity_type = [:get_constant name=entity_person]"""

        return self.query("""
        SELECT DISTINCT pi.person_id, pi.birth_date,
                        at.account_id, eei.external_id,
          at.ou_id, at.affiliation %(ecols)s
        FROM
          [:table schema=cerebrum name=person_info] pi
          JOIN [:table schema=cerebrum name=account_type] at
            ON at.person_id = pi.person_id AND
               at.priority = (
                 SELECT MIN(priority)
                 FROM [:table schema=cerebrum name=account_type] at2
                 WHERE at2.person_id = pi.person_id)
          %(efrom)s
          """ % locals(), {'spread': spread, 'idtype': idtype}, fetchall=False)

    def search_person_names(self, person_id=None, name_variant=None,
                            source_system=None, name=None, exact_match=True,
                            case_sensitive=True):
        """Collect person names from the db matching the specified criteria.

        The goal of this method is to search for names, rather than person_ids,
        although both are returned in the result set.

        person_id, name_variant and source_system can be sequences. The rest
        are scalars only.

        @param person_id:
          Collect names for these person_ids.

        @param name_variant:
          Collect specified name variants (first, last, full, etc.)

        @param source_system:
          Collect names from the specified authoritative source(s) only.

        @param name:
          Collect data for the specified name (pattern). name may contain SQL
          wildcard characters. '?' will be auto-mapped to '_', '*' to '%'.

        @param exact_match:
          Only meaningful when L{name} is set. This flag determines whether the
          name searching is to be performed exactly, or by wildcard (SQL LIKE).

        @param case_sensitive:
          Only meaningful when L{name} is set. This flag determines whether a
          lowercasing is applied to the name.
        """

        binds = dict()
        where = list()
        if person_id is not None:
            where.append(argument_to_sql(
                person_id, "pn.person_id", binds, int))
        if name_variant is not None:
            where.append(
                argument_to_sql(name_variant, "pn.name_variant", binds,
                                int))
        if source_system is not None:
            where.append(argument_to_sql(source_system, "pn.source_system",
                                         binds, int))
        #
        # the name attirbute is quite complex, since multiple filters interact
        if name is not None:
            if not case_sensitive:
                name_pattern = prepare_string(name, six.text_type.lower)
                column_name = "LOWER(pn.name)"
            else:
                name_pattern = prepare_string(name, None)
                column_name = "pn.name"

            equality_func = "="
            if not exact_match:
                equality_func = "LIKE"
                if name_pattern.find('%') == -1:
                    name_pattern = '%' + name_pattern + '%'

            # Now, putting it all together
            where.append("(%s %s :name)" % (column_name, equality_func))
            binds["name"] = name_pattern

        where = " AND ".join(where) or ""
        if where:
            where = "WHERE " + where

        return self.query("""
        SELECT pn.person_id, pn.name_variant, pn.source_system, pn.name
        FROM [:table schema=cerebrum name=person_name] pn
        """ + where, binds)
    # end search_names

    def search(self, spread=None, name=None, description=None, birth_date=None,
               entity_id=None, exclude_deceased=False, name_variants=[],
               first_name=None, last_name=None):
        """
        Retrieves a list over Persons filtered by the given criterias.

        If no criteria is given, all persons are returned. ``name``,
        ``description`` and ``birth_date`` should be strings if given.
        ``spread`` can be either string or int, ``entity_id`` can be an int or
        a list of ints.

        Wildcards * and ? are expanded for "any chars" and "one char".

        Returns a list of tuples with the info (person_id, name, description).

        ``name_variants`` is a list of name_variant constants.  If given, the
        returned rows will include these names instead of name.  The column
        names will be the name of the variant lowercased with _name appended.
        Examples: first_name, last_name, full_name.
        """

        tables = []
        where = []
        selects = []
        tables.append("[:table schema=cerebrum name=person_info] pi")
        tables.append("[:table schema=cerebrum name=person_name] pn")
        where.append("pi.person_id=pn.person_id")

        binds = {
            'entity_type': int(self.const.entity_person),
        }

        if not name_variants:
            selects.append("pn.name AS name")
        else:
            for v in name_variants:
                vid = int(v)
                vname = "%s_name" % six.text_type(v).lower()
                selects.append("pn_%s.name AS %s" % (vid, vname))
                tables.append(
                    "[:table schema=cerebrum name=person_name] pn_%s" %
                    vid)
                where.append("pn_%s.name_variant = %i" % (vid, vid))
                where.append("pi.person_id=pn_%s.person_id" % vid)

                # restrict search based on first name (if given)
                if first_name is not None and vname == "first_name":
                    first_name = prepare_string(first_name)
                    where.append("LOWER(pn_%s.name) LIKE :first_name" % (vid,))
                    binds['first_name'] = first_name

                # restrict search based on last name (if given)
                if last_name is not None and vname == "last_name":
                    last_name = prepare_string(last_name)
                    where.append("LOWER(pn_%s.name) LIKE :last_name" % (vid,))
                    binds['last_name'] = last_name

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("pi.person_id=es.entity_id")
            where.append("es.entity_type=:entity_type")
            try:
                spread = int(spread)
            except (TypeError, ValueError):
                spread = prepare_string(spread)
                tables.append("[:table schema=cerebrum name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :spread")
            else:
                where.append("es.spread=:spread")
            binds['spread'] = spread

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(pn.name) LIKE :name")
            binds['name'] = name

        if birth_date is not None:
            birth_date = prepare_string(birth_date)
            where.append("birth_date = :birth_date")
            binds['birth_date'] = birth_date

        if description is not None:
            description = prepare_string(description)
            where.append("LOWER(pi.description) LIKE :description")
            binds['description'] = description

        if exclude_deceased:
            where.append("pi.deceased_date IS NULL")

        if entity_id is not None:
            where.append(
                argument_to_sql(
                    entity_id,
                    "pi.person_id",
                    binds,
                    int))

        where_str = ""
        if where:
            where_str = "WHERE %s" % " AND ".join(where)

        selects.insert(0, """
        SELECT DISTINCT pi.person_id AS person_id,
                pi.description AS description,
                pi.birth_date AS birth_date,
                pi.gender AS gender
                """)
        select_str = ", ".join(selects)
        from_str = "FROM %s" % ", ".join(tables)
        return self.query("%s %s %s" % (select_str, from_str, where_str),
                          binds)

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.get_name(self.const.system_cached,
                                 self.const.name_full)
        return '<unbound person>'
