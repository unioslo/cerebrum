# -*- coding: iso-8859-1 -*-
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
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityAddress, EntityQuarantine, \
     EntityExternalId


class OU(EntityContactInfo, EntityExternalId, EntityAddress,
         EntityQuarantine, Entity):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'acronym', 'short_name', 'display_name',
                      'sort_name')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(OU)
        self.__updated = []

    def populate(self, name, acronym=None, short_name=None,
                 display_name=None, sort_name=None, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_ou)
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
        self.name = name
        self.acronym = acronym
        self.short_name = short_name
        self.display_name = display_name
        self.sort_name = sort_name

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=ou_info]
              (entity_type, ou_id, name, acronym, short_name, display_name,
               sort_name)
            VALUES (:e_type, :ou_id, :name, :acronym, :short_name, :disp_name,
                    :sort_name)""",
                         {'e_type': int(self.const.entity_ou),
                          'ou_id': self.entity_id,
                          'name': self.name,
                          'acronym': self.acronym,
                          'short_name': self.short_name,
                          'disp_name': self.display_name,
                          'sort_name': self.sort_name})
            self._db.log_change(self.entity_id, self.const.ou_create, None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=ou_info]
            SET name=:name, acronym=:acronym, short_name=:short_name,
                display_name=:disp_name, sort_name=:sort_name
            WHERE ou_id=:ou_id""",
                         {'name': self.name,
                          'acronym': self.acronym,
                          'short_name': self.short_name,
                          'disp_name': self.display_name,
                          'sort_name': self.sort_name,
                          'ou_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.ou_mod, None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.name == self.name) and
                     (other.acronym == self.acronym) and
                     (other.short_name == self.short_name) and
                     (other.display_name == self.display_name) and
                     (other.sort_name == self.sort_name))
        if cereconf.DEBUG_COMPARE:
            print "OU.__eq__ = %s" % identical
        return identical

    def new(self, name, acronym=None, short_name=None, display_name=None,
            sort_name=None):
        """Register a new OU."""
        self.populate(name, acronym, short_name, display_name, sort_name)
        self.write_db()
        self.find(self.entity_id)

    def find(self, ou_id):
        """Associate the object with the OU whose identifier is OU_ID.

        If OU_ID isn't an existing OU identifier,
        NotFoundError is raised."""
        self.__super.find(ou_id)
        (self.ou_id, self.name, self.acronym, self.short_name,
         self.display_name, self.sort_name) = self.query_1("""
        SELECT ou_id, name, acronym, short_name, display_name, sort_name
        FROM [:table schema=cerebrum name=ou_info]
        WHERE ou_id=:ou_id""", {'ou_id': ou_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_parent(self, acronym, perspective, parent_id):
        pid = "AND s.parent_id=:parent_id"
        if parent_id is None:
            pid = "AND s.parent_id IS NULL"
        ou_id = self.query_1("""
        SELECT o.ou_id
        FROM [:table schema=cerebrum name=ou_structure] s,
             [:table schema=cerebrum name=ou_info] o
        WHERE s.ou_id = o.ou_id AND s.perspective=:perspective
             %s AND o.acronym=:acronym""" % pid,
                                 {'perspective': int(perspective),
                                  'acronym': acronym,
                                  'parent_id': parent_id})
        self.find(ou_id)

    def get_parent(self, perspective):
        return self.query_1("""
        SELECT parent_id
        FROM [:table schema=cerebrum name=ou_structure]
        WHERE ou_id=:ou_id AND  perspective=:perspective""",
                            {'ou_id': self.entity_id,
                             'perspective': int(perspective)})
    # end get_parent

    def _get_item_languages(self, item_name, merge):
        """
        Fetch ITEM_NAME's values with respective languages.

        ITEM_NAME can be 'name', 'acronym', 'short_name', 'display_name',
        'sort_name'.

        MERGE's values can be 'default', 'extra' or 'both', meaning that
        language information is fetched from tables ou_info only,
        ou_name_language only, or both respectively.

        This function is not meant to be directly accessible from outside
        OU. Write a suitable interface, like get_names(), if you need it.
        """
        
        if item_name not in ("name", "acronym", "short_name",
                             "display_name", "sort_name"):
            raise Exception, ("Aiee! Merging invalid item in SQL (%s)" %
                              item_name)
        # fi

        result = []
        if merge in ("default", "both"):
            # Note that we could have obtained this information directly
            # from SELF, but it is bad carma to return a heterogeneous list
            # (tuples of strings and db_rows (below)).
            # This way the client code can safely work with the result as a
            # list of db rows.
            result.append(self.query_1("""
            SELECT %s, '' as language
            FROM [:table schema=cerebrum name=ou_info]
            WHERE ou_id=:ou_id""" % item_name,
                                    {"ou_id": self.entity_id,
                                     "item": item_name}))
        # fi

        if merge in ("extra", "both"):
            result.extend(self.query("""
            SELECT onl.%s as %s, lc.code_str as language
            FROM [:table schema=cerebrum name=ou_name_language] onl,
                 [:table schema=cerebrum name=language_code] lc
            WHERE onl.ou_id = :ou_id AND
                  onl.language_code = lc.code""" % (item_name,
                                                    item_name),
                                     {"ou_id": self.entity_id,
                                      "item": item_name}))
        # fi

        return result
    # end _get_item_languages
        
    def get_names(self):
        """
        Returns all names in all languages for this OU
        """

        return self._get_item_languages(item_name="name",
                                        merge="both")
    # end get_names

    def get_acronyms(self):
        """
        Returns all acronyms in all languages for this OU
        """

        return self._get_item_languages(item_name="acronym",
                                        merge="both")
    # end get_acronyms

    def structure_path(self, perspective):
        """Return a string indicating OU's structural placement.

        Recursively collect 'acronym' of OU and its parents (as they
        are modeled in 'perspective'); return a string with a
        '/'-delimited list of these acronyms, most specific OU first.

        """
        temp = self.__class__(self._db)
        temp.find(self.entity_id)
        components = []
        visited = []
        while True:
            # Detect infinite loops
            if temp.entity_id in visited:
                raise RuntimeError, "DEBUG: Loop detected: %r" % visited
            visited.append(temp.entity_id)
            # Append this node's acronym (if it is non-NULL) to
            # 'components'.
            # TBD: Is this the correct way to handle NULL acronyms?
            if temp.acronym is not None:
                components.append(temp.acronym)
            # Find parent, end search if parent is either NULL or the
            # same node we're currently at.
            parent_id = temp.get_parent(perspective)
            if (parent_id is None) or (parent_id == temp.entity_id):
                break
            temp.clear()
            temp.find(parent_id)
        return "/".join(components)

    def unset_parent(self, perspective):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=ou_structure]
        WHERE ou_id=:e_id AND perspective=:perspective""",
                     {'e_id': self.entity_id,
                      'perspective': int(perspective)})
        self._db.log_change(self.entity_id, self.const.ou_unset_parent, None,
                            change_params={'perspective': int(perspective)})

    def set_parent(self, perspective, parent_id):
        """Set the parent of this OU to ``parent_id`` in ``perspective``."""
        try:
            self.get_parent(perspective)
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
        self._db.log_change(self.entity_id, self.const.ou_set_parent,
                            parent_id,
                            change_params={'perspective': int(perspective)})

    def list_children(self, perspective, entity_id=None, recursive=False):
        if not entity_id:
            entity_id = self.entity_id
        ret = []
        tmp = self.query("""
        SELECT ou_id FROM [:table schema=cerebrum name=ou_structure]
        WHERE parent_id=:e_id AND perspective=:perspective""",
                          {'e_id': entity_id,
                           'perspective': int(perspective)})
        ret.extend(tmp)
        if recursive:
            for r in tmp:
                ret.extend(self.list_children(perspective, r['ou_id'],
                                              recursive))
        return ret

    def list_all(self):
        return self.query("""
        SELECT ou_id FROM [:table schema=cerebrum name=ou_info]""")

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

    def search(self, spread=None, name=None, acronym=None,
               short_name=None, display_name=None, sort_name=None):
        """Retrives a list of OUs filtered by the given criterias.
        
        Returns a list of tuples with the info (ou_id, name).
        If no criteria is given, all OUs are returned. ``name``, ``acronum``,
        ``short_name``, ``display_name`` and ``sort_name`` should be string if
        given. ``spread`` can be either string or int. Wildcards * and ? are
        expanded for "any chars" and "one char"."""

        def prepare_string(value):
            value = value.replace("*", "%")
            value = value.replace("?", "_")
            value = value.lower()
            return value

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=ou_info] oi")

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("oi.ou_id=es.entity_id")
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

        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(oi.name) LIKE :name")

        if acronym is not None:
            acronym = prepare_string(acronym)
            where.append("LOWER(oi.acronym) LIKE :acronym")

        if short_name is not None:
            short_name = prepare_string(short_name)
            where.append("LOWER(oi.short_name) LIKE :short_name")

        if display_name is not None:
            display_name = prepare_string(display_name)
            where.append("LOWER(oi.display_name) LIKE :display_name")
        
        if sort_name is not None:
            sort_name = prepare_string(sort_name)
            where.append("LOWER(oi.sort_name) LIKE :sort_name")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT oi.ou_id AS ou_id, oi.name AS name
        FROM %s %s""" % (','.join(tables), where_str),
            {'spread': spread, 'entity_type': int(self.const.entity_ou),
             'name': name, 'acronym': acronym, 'short_name': short_name,
             'display_name': display_name, 'sort_name': sort_name})

# arch-tag: 45bda60e-7677-4c5e-a1ba-f07621d9c791
