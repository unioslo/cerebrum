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
"""Organisational Unit implementation.

This module implements the functionality for one of the basic elements of
Cerebrum - organizational units (OUs). They represent an element of an
organization's tree, typically an administrative unit of some sort (school,
faculty, etc).

OUs are organized into trees. Trees are specific to a given authoritative data
source, called perspective. An OU may be in different parts of the
organizational trees in different perspectives.
"""

from __future__ import unicode_literals

import six

from Cerebrum import Utils
from Cerebrum.Utils import prepare_string
from Cerebrum import Errors
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.Entity import EntityAddress
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Entity import EntityExternalId
from Cerebrum.Entity import EntitySpread
from Cerebrum.Entity import EntityNameWithLanguage


Entity_class = Utils.Factory.get("Entity")


@six.python_2_unicode_compatible
class OU(EntityContactInfo, EntityExternalId, EntityAddress,
         EntityQuarantine, EntitySpread, EntityNameWithLanguage,
         Entity_class):

    __read_attr__ = ('__in_db',)
    __deprecated_names = ("name", "acronym", "short_name", "display_name",
                          "sort_name")

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(OU)
        self.__updated = []

    def populate(self):
        Entity_class.populate(self, self.const.entity_ou)
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

    def __getattribute__(self, name):
        """Issue warnings for deprecated API usage.

        This should help us pinpoint deprecated usage patterns for OU's name
        attributes. This hook can be safely removed, once we've cleaned up the
        code base.
        """

        if name not in OU.__deprecated_names:
            return super(OU, self).__getattribute__(name)

        name_map = {"name": self.const.ou_name,
                    "acronym": self.const.ou_name_acronym,
                    "short_name": self.const.ou_name_short,
                    "display_name": self.const.ou_name_display, }
        logger = Utils.Factory.get_logger()
        logger.warn("Deprecated usage of OU:"
                    " OU.%s cannot be accessed directly."
                    " Use get/add/delete_name_with_language", name)
        # For the "unspecified" case we assume Norwegian bokmål.
        return self.get_name_with_language(name_map[name],
                                           self.const.language_nb,
                                           default='')

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ou_info]
              (entity_type, ou_id)
            VALUES (:e_type, :ou_id)""",
                         {'e_type': int(self.const.entity_ou),
                          'ou_id': self.entity_id, })
            self._db.log_change(self.entity_id, self.clconst.ou_create, None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False

        own_names = set((r["name_variant"], r["name_language"], r["name"])
                        for r in
                        self.search_name_with_language(
                            entity_id=self.entity_id))
        other_names = set((r["name_variant"], r["name_language"], r["name"])
                          for r in
                          other.search_name_with_language(
                              entity_id=self.entity_id))
        return own_names == other_names

    def new(self):
        """Register a new OU."""
        self.populate()
        self.write_db()
        self.find(self.entity_id)

    def delete(self):
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=ou_info]
            WHERE ou_id = :ou_id""", {'ou_id': self.entity_id})
            self._db.log_change(self.entity_id, self.clconst.ou_del, None)
        self.__super.delete()

    def find(self, ou_id):
        """Associate the object with the OU whose identifier is OU_ID.

        If OU_ID isn't an existing OU identifier, NotFoundError is raised.
        """
        self.__super.find(ou_id)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def get_parent(self, perspective):
        return self.query_1("""
        SELECT parent_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE ou_id=:ou_id AND  perspective=:perspective""",
                            {'ou_id': self.entity_id,
                             'perspective': int(perspective)})

    def local_it_contact(self, perspective):
        """Return the 'LOCAL-IT' contact of the nearest OU which has one

        :rtype: list[dict]
        """
        try:
            parents = self.list_ou_path(perspective)
        except Errors.NotFoundError:
            # If this happens, some OU in the path does not exist in the
            # ou_structure table (which means there is an error in the OU
            # hierarchy), but this method should probably still work?
            return []

        ou = self.__class__(self._db)
        for parent in parents:
            ou.clear()
            ou.find(parent)
            contact_infos = ou.get_contact_info(type=self.const.contact_lit)
            if contact_infos:
                ret = []
                for row in contact_infos:
                    contact_info = dict(row)
                    contact_info['from_ou_id'] = parent
                    ret.append(contact_info)
                return ret
        return []

    def list_ou_path(self, perspective):
        """Return a list indicating OU's structural placement.

        Recursively collect 'entity_id' of OU and its parents (as they
        are modeled in 'perspective'); return a list with most specific OU
        first.

        """
        temp = self.__class__(self._db)
        temp.find(self.entity_id)

        visited = list()
        while True:
            # Detect infinite loops
            if temp.entity_id in visited:
                raise RuntimeError("DEBUG: Loop detected: %r" % visited)
            visited.append(temp.entity_id)
            # Find parent, end search if parent is either NULL or the
            # same node we're currently at.
            parent_id = temp.get_parent(perspective)
            if (parent_id is None) or (parent_id == temp.entity_id):
                break
            temp.clear()
            temp.find(parent_id)
        return visited

    def unset_parent(self, perspective):
        binds = {'ou_id': self.entity_id,
                 'perspective': int(perspective)}
        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=ou_structure]
          WHERE {where}
        )
        """.format(where=' AND '.join('{0}=:{0}'.format(x) for x in binds))
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
        DELETE FROM [:table schema=cerebrum name=ou_structure]
        WHERE ou_id=:ou_id AND perspective=:perspective"""
        self.execute(delete_stmt, binds)
        self._db.log_change(self.entity_id,
                            self.clconst.ou_unset_parent,
                            None,
                            change_params={'perspective': int(perspective)})

    def set_parent(self, perspective, parent_id):
        """Set the parent of this OU to ``parent_id`` in ``perspective``."""
        try:
            old_parent = self.get_parent(perspective)
            if old_parent == parent_id:
                # Don't need to change parent_id to the same parent_id
                return
            self.execute("""
            UPDATE [:table schema=cerebrum name=ou_structure]
            SET parent_id=:parent_id
            WHERE ou_id=:e_id AND perspective=:perspective""",
                         {'e_id': self.entity_id,
                          'perspective': int(perspective),
                          'parent_id': parent_id})
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ou_structure]
              (ou_id, perspective, parent_id)
            VALUES (:e_id, :perspective, :parent_id)""",
                         {'e_id': self.entity_id,
                          'perspective': int(perspective),
                          'parent_id': parent_id})
        self._db.log_change(self.entity_id, self.clconst.ou_set_parent,
                            parent_id,
                            change_params={'perspective': int(perspective)})

    def list_children(self, perspective, entity_id=None, recursive=False):
        if not entity_id:
            entity_id = self.entity_id
        tmp = self.query("""
        SELECT ou_id FROM [:table schema=cerebrum name=ou_structure]
        WHERE parent_id=:e_id AND perspective=:perspective""",
                         {'e_id': entity_id,
                          'perspective': int(perspective)},
                         fetchall=False)
        if recursive:
            ou_ids = []
            for row in tmp:
                ou_ids.append(row['ou_id'])
                ou_ids.extend(self.list_children(perspective,
                                                 row['ou_id'],
                                                 True))
            return ou_ids
        return [r['ou_id'] for r in tmp]

    def get_structure_mappings(self, perspective):
        """Return list of ou_id -> parent_id connections in ``perspective``."""
        return self.query("""
        SELECT ou_id, parent_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE perspective=:perspective""", {'perspective': int(perspective)})

    def root(self):
        # FIXME: Doesn't check perspective. Documentation should also
        # make it clear that a perspective can have more than one root.
        #
        # Is this to be tought of as a method or class method? Even
        # though a perspective can have many roots, any given OU will
        # only have one root inside a perspective, if the OU is at all
        # represented in that perspective.
        return self.query("""
        SELECT ou_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE parent_id IS NULL""")

    def search(self, spread=None, filter_quarantined=False):
        """Retrives a list of OUs filtered by the given criteria.

        Note that acronyms and other name variants is not a part of the basic
        OU table, but could be searched for through
        L{EntityNameWithLanguage.search_name_with_language}.

        If no criteria is given, all OUs are returned.
        """

        where = []
        binds = dict()
        tables = ["[:table schema=cerebrum name=ou_info] oi", ]

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("oi.ou_id=es.entity_id")
            where.append("es.entity_type=:entity_type")
            binds["entity_type"] = int(self.const.entity_ou)
            try:
                spread = int(spread)
            except (TypeError, ValueError):
                spread = prepare_string(spread)
                tables.append("[:table schema=cerebrum name=spread_code] sc")
                where.append("es.spread=sc.code")
                where.append("LOWER(sc.code_str) LIKE :spread")
            else:
                where.append("es.spread=:spread")
            binds["spread"] = spread

        if filter_quarantined:
            where.append("""
            (NOT EXISTS (SELECT 1
                         FROM
                          [:table schema=cerebrum name=entity_quarantine] eq
                         WHERE oi.ou_id=eq.entity_id))
            """)

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT oi.ou_id
        FROM %s %s""" % (','.join(tables), where_str), binds)

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.display_name
        return '<unbound ou>'
