# -*- coding: utf-8 -*-
# Copyright 2003-2018 University of Oslo, Norway
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


from __future__ import unicode_literals

import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory, prepare_string, argument_to_sql
from Cerebrum.Entity import EntityName, EntitySpread

Entity_class = Factory.get("Entity")


@six.python_2_unicode_compatible
class Disk(EntitySpread, Entity_class):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('host_id', 'path', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Disk)
        self.__updated = []

    def populate(self, host_id, path, description, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_disk)
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
        self.host_id = host_id
        self.path = path
        self.description = description

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
        binds = {'path': self.path,
                 'host_id': self.host_id,
                 'disk_id': self.entity_id,
                 'description': self.description}

        if is_new:
            binds['e_type'] = int(self.const.entity_disk)
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=disk_info]
              (entity_type, host_id, disk_id, path, description)
            VALUES (:e_type, :host_id, :disk_id, :path, :description)
                    """, binds)
            self._db.log_change(self.entity_id, self.clconst.disk_add, None,
                                change_params={'host_id': self.host_id,
                                               'path': self.path})
        else:
            exists_stmt = """
            SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=disk_info]
            WHERE {where}
            )
            """.format(where=' AND '.join('{0}=:{0}'.format(x) for x in binds),
                       table=table)
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=disk_info]
                SET path=:path, description=:description, host_id=:host_id
                WHERE disk_id=:disk_id"""
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.disk_mod,
                                    None,
                                    change_params={'host_id': self.host_id,
                                                   'path': self.path})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, Disk)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.path == self.path) and
                     (other.description == self.description))
        return identical

    def find(self, disk_id):
        """Associate the object with the Disk whose identifier is disk_id.

        If disk_id isn't an existing Disk identifier,
        NotFoundError is raised."""
        self.__super.find(disk_id)
        (self.host_id, self.path, self.description) = self.query_1("""
        SELECT host_id, path, description
        FROM [:table schema=cerebrum name=disk_info]
        WHERE disk_id=:disk_id""", {'disk_id': disk_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_path(self, path, host_id=None):
        """Attempt to uniquely identify the disk."""
        host_qry = ""
        if host_id is not None:
            host_qry = "AND host_id=:host_id"
        entity_id = self.query_1("""
        SELECT disk_id
        FROM [:table schema=cerebrum name=disk_info]
        WHERE path=:path %s""" % host_qry,
                                 {'path': path,
                                  'host_id': host_id})
        self.find(entity_id)

    def list(self, host_id=None, filter_expired=False, spread=None):
        spread_where = expire_where = ""
        where = []
        if host_id is not None:
            where.append("host_id=:host_id")
        if filter_expired:
            expire_where = """AND (ai.expire_date IS NULL OR
                                   ai.expire_date > [:now])"""
        if spread is not None:
            spread_where = "AND ah.spread=:spread"
            spread = int(spread)
        if where:
            where = "WHERE " + " AND ".join(where)
        else:
            where = ""
        # Note: This syntax requires Oracle >= 9
        return self.query("""
        SELECT count(ah.account_id), ah.spread,
               di.disk_id, di.host_id, di.path
        FROM [:table schema=cerebrum name=disk_info] di
          LEFT JOIN ([:table schema=cerebrum name=homedir] hd
                     JOIN [:table schema=cerebrum name=account_home] ah
                       ON hd.homedir_id=ah.homedir_id %s
                     JOIN [:table schema=cerebrum name=account_info] ai
                       ON ah.account_id=ai.account_id %s)
            ON di.disk_id=hd.disk_id
        %s
        GROUP BY di.disk_id, di.host_id, di.path, ah.spread""" %
                          (spread_where, expire_where, where),
                          {'host_id': host_id, 'spread': spread})

    def delete(self):
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=disk_info]
            WHERE disk_id = :d_id""", {'d_id': self.entity_id})
            self._db.log_change(self.entity_id, self.clconst.disk_del, None,
                                change_params={'host_id': self.host_id,
                                               'path': self.path})
        self.__super.delete()

    def search(self, spread=None, host_id=None, path=None, description=None):
        """Retrives a list of Disks filtered by the given criterias.

        Returns a list of tuples with the info (disk_id, path, description).
        If no criteria is given, all persons are returned. ``path`` and
        ``description`` should be strings if given. ``host_id`` should be int.
        ``spread`` can be either string or int. Wildcards * and ? are expanded
        for "any chars" and "one char"."""

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=disk_info] di")

        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("di.disk_id=es.entity_id")
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

        if host_id is not None:
            where.append("di.host_id=:host_id")

        if path is not None:
            path = prepare_string(path)
            where.append("LOWER(di.path) LIKE :path")

        if description is not None:
            description = prepare_string(description)
            where.append("LOWER(di.description) LIKE :description")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT DISTINCT di.disk_id AS disk_id, di.path AS path,
                di.description AS description
        FROM %s %s""" % (','.join(tables), where_str),
                          {'spread': spread,
                           'entity_type': int(self.const.entity_disk),
                           'host_id': host_id,
                           'path': path,
                           'description': description})

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.path
        return '<unbound disk>'

    def has_quota(self):
        """
        Abstract API for checking if the disk has disk quotas.

        The default is `False` - i.e. no disk quota.
        """
        return False

    def get_default_quota(self):
        """
        Abstract API for getting disk quota.

        The default quota is `None` - i.e. no quota.
        """
        return None


@six.python_2_unicode_compatible
class Host(EntityName, EntitySpread, Entity_class):
    # TODO: Move into it's own Host.py
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Host)
        self.__updated = []

    def populate(self, name, description, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_host)
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
        self.name = name
        self.description = description

    def illegal_name(self, name):
        """Return a string with error message if host name is illegal"""
        return False

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""

        self.__super.write_db()
        if not self.__updated:
            return
        if 'name' in self.__updated:
            tmp = self.illegal_name(self.name)
            if tmp:
                raise self._db.IntegrityError("Illegal host name: %s" % tmp)

        is_new = not self.__in_db
        binds = {'host_id': self.entity_id,
                 'description': self.description}

        if is_new:
            binds['e_type'] = int(self.const.entity_host)
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=host_info]
              (entity_type, host_id, description)
            VALUES (:e_type, :host_id, :description)
                    """, binds)
            self._db.log_change(self.entity_id, self.clconst.host_add, None,
                                change_params={'name': self.name})
            self.add_entity_name(self.const.host_namespace, self.name)
        else:
            exists_stmt = """
            SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=host_info]
            WHERE {where}
            )
            """.format(where=' AND '.join('{0}=:{0}'.format(x) for x in binds),
                       table=table)
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                UPDATE [:table schema=cerebrum name=host_info]
                SET description=:description
                WHERE host_id=:host_id"""
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.host_mod,
                                    None,
                                    change_params={'name': self.name})
                if 'name' in self.__updated:
                    self.update_entity_name(self.const.host_namespace,
                                            self.name)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, Host)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.name == self.name) and
                     (other.description == self.description))
        return identical

    def find(self, host_id):
        """Associate the object with the Host whose identifier is host_id.

        If host_id isn't an existing Host identifier,
        NotFoundError is raised."""
        self.__super.find(host_id)
        (self.host_id, self.description) = self.query_1("""
        SELECT host_id, description
        FROM [:table schema=cerebrum name=host_info]
        WHERE host_id=:host_id""", {'host_id': host_id})
        self.name = self.get_name(self.const.host_namespace)
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        """Associate the object with the Host whose name is name.  If
        name isn't an existing Host identifier, NotFoundError is
        raised.

        """
        EntityName.find_by_name(self, name, self.const.host_namespace)

    def delete(self):
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=host_info]
            WHERE host_id = :host_id""", {'host_id': self.entity_id})
            self._db.log_change(self.entity_id, self.clconst.host_del, None,
                                change_params={'old_name': self.name})
        self.__super.delete()

    def search(self, host_id=None, name=None, description=None):
        """Retrieves a list of Hosts filtered by the given criterias.

        If no criteria is given, all hosts are returned. ``name`` and
        ``description`` should be strings if given. Wildcards * and ? are
        expanded for "any chars" and "one char".

        :return list:
            A list of tuples/db_rows with fields: (host_id, name, description)
        """
        where = list()
        binds = dict()

        query_fmt = """
        SELECT DISTINCT hi.host_id, en.entity_name AS name, hi.description
        FROM [:table schema=cerebrum name=host_info] hi
        JOIN [:table schema=cerebrum name=entity_name] en
          ON hi.host_id = en.entity_id AND
             en.value_domain = [:get_constant name=host_namespace]
        {where!s}
        """

        if host_id is not None:
            where.append(argument_to_sql(host_id, 'hi.host_id', binds, int))

        if name is not None:
            where.append("LOWER(en.entity_name) LIKE :name")
            binds['name'] = prepare_string(name.lower())

        if description is not None:
            where.append("LOWER(hi.description) LIKE :desc")
            binds['desc'] = prepare_string(description.lower())

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query(query_fmt.format(where=where_str), binds)

    def __str__(self):
        if hasattr(self, 'entity_id'):
            return self.name
        return '<unbound host>'
