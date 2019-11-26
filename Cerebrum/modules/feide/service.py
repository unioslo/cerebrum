#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

import re

from Cerebrum.Utils import Factory, prepare_string, argument_to_sql


Entity_class = Factory.get("Entity")


class FeideService(Entity_class):
    """ Keeps track of Feide services. """

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('feide_id', 'name')

    def clear(self):
        self.__super.clear()
        self.clear_class(FeideService)
        self.__updated = []

    def populate(self, feide_id, name):
        Entity_class.populate(self, self.const.entity_feide_service)
        try:
            if not self.__in_db:
                raise RuntimeError('populate() called multiple times.')
        except AttributeError:
            self.__in_db = False
        self.feide_id = feide_id
        self.name = name

    def write_db(self):
        """Sync instance with Cerebrum database."""
        self.__super.write_db()
        if not self.__updated:
            return None
        binds = {'service_id': self.entity_id,
                 'feide_id': self.feide_id,
                 'name': self.name}
        is_new = not self.__in_db
        if is_new:
            insert_stmt = """
            INSERT INTO [:table schema=cerebrum name=feide_service_info]
              (service_id, feide_id, name)
            VALUES (:service_id, :feide_id, :name)"""
            self.execute(insert_stmt, binds)
            self._db.log_change(self.entity_id,
                                self.clconst.feide_service_add,
                                None,
                                change_params=binds)
        else:
            exists_stmt = """
              SELECT EXISTS (
              SELECT 1
              FROM [:table schema=cerebrum name=feide_service_info]
              WHERE service_id=:service_id AND
                    feide_id=:feide_id AND
                    name=:name
              )
            """
            if not self.query_1(exists_stmt, binds):
                # True positive
                update_stmt = """
                  UPDATE [:table schema=cerebrum name=feide_service_info]
                  SET feide_id=:feide_id, name=:name
                  WHERE service_id=:service_id
                """
                self.execute(update_stmt, binds)
                self._db.log_change(self.entity_id,
                                    self.clconst.feide_service_mod,
                                    None,
                                    change_params={'feide_id': self.feide_id,
                                                   'name': self.name})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Delete associated authentication levels"""
        if self.__in_db:
            # Nuke any associated authentication levels
            fsal = FeideServiceAuthnLevelMixin(self._db)
            for authn in fsal.search_authn_level(service_id=self.entity_id):
                fsal.remove_authn_level(**authn)
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=feide_service_info]
            WHERE service_id = :service_id""", {'service_id': self.entity_id})
            self._db.log_change(
                self.entity_id, self.clconst.feide_service_del, None,
                change_params={'feide_id': self.feide_id,
                               'name': self.name})
        self.__super.delete()

    def illegal_name(self, name, max_length=128):
        """ Return a string with error message if service name is illegal. """
        if not name:
            return "Must specify Feide service name"
        if len(name) > max_length:
            return "Name '{}' too long (max {} characters)".format(
                name, max_length)
        pattern = r'^[a-zA-Z0-9_.-]*$'
        if not re.match(pattern, name):
            return "Name must match {}".format(pattern)
        return False

    def find(self, service_id):
        """ Associate the object with the Feide service whose identifier
        is service_id. """
        self.__super.find(service_id)
        (self.feide_id, self.name) = self.query_1("""
        SELECT feide_id, name
        FROM [:table schema=cerebrum name=feide_service_info]
        WHERE service_id=:service_id""", {'service_id': service_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        """ Look up a Feide service by name. """
        service_id = self.query_1("""
        SELECT service_id
        FROM [:table schema=cerebrum name=feide_service_info]
        WHERE name=:name""", {'name': name})
        self.find(service_id)

    def search(self, feide_id=None, name=None):
        tables = ["[:table schema=cerebrum name=feide_service_info] fsi"]
        where = []
        if name is not None:
            name = prepare_string(name)
            where.append("LOWER(fsi.name) LIKE :name")
        if feide_id is not None:
            where.append("fsi.feide_id=:feide_id")
        where_str = "WHERE " + " AND ".join(where) if where else ""
        binds = {'feide_id': feide_id, 'name': name}
        return self.query("""
        SELECT DISTINCT fsi.service_id AS service_id,
                        fsi.feide_id AS feide_id,
                        fsi.name AS name
        FROM %s %s""" % (','.join(tables), where_str), binds)

    def get_person_to_authn_level_map(self):
        """ Creates a mapping from person_id to (feide_id, level). """
        gr = Factory.get('Group')(self._db)
        co = Factory.get('Constants')(self._db)

        authn_level_query = """
        SELECT DISTINCT fsal.service_id AS service_id,
                        fsi.feide_id AS feide_id,
                        fsal.entity_id AS entity_id,
                        fsal.level AS level,
                        ei.entity_type AS entity_type
        FROM [:table schema=cerebrum name=feide_service_authn_level] fsal,
             [:table schema=cerebrum name=feide_service_info] fsi,
             [:table schema=cerebrum name=entity_info] ei
        WHERE fsal.entity_id=ei.entity_id
        AND fsal.service_id=fsi.service_id"""

        def account_ids_to_person_ids(account_ids):
            """ Takes a sequence of account IDs and returns their owners ID
            if the owner is a person. """
            if not account_ids:
                return []
            binds = {}
            where = [
                argument_to_sql(account_ids, 'ai.account_id', binds, int),
                'ai.owner_id=ei.entity_id',
                argument_to_sql(
                    co.entity_person, 'ei.entity_type', binds, int)]
            where_str = " AND ".join(where)
            sql = """
            SELECT DISTINCT ai.owner_id
            FROM [:table schema=cerebrum name=account_info] ai,
                 [:table schema=cerebrum name=entity_info] ei
            WHERE {}""".format(where_str)
            return [x['owner_id'] for x in self.query(sql, binds)]

        def make_entry(data):
            return (data['feide_id'], data['level'])

        groups = []
        persons = {}
        # Fetch authentication levels for groups and persons
        for authn in self.query(authn_level_query):
            # Persons can be added directly
            if authn['entity_type'] == co.entity_person:
                persons.setdefault(authn['entity_id'], set()).add(
                    make_entry(authn))
            # ...while groups require extra processing
            elif authn['entity_type'] == co.entity_group:
                groups.append(authn)

        for group in groups:
            # We flatten group memberships and only fetch persons and accounts
            members = gr.search_members(group_id=group['entity_id'],
                                        indirect_members=True,
                                        member_type=[co.entity_person,
                                                     co.entity_account])
            account_ids = []
            for member in members:
                # Persons can be added directly
                if member['member_type'] == co.entity_person:
                    persons.setdefault(member['member_id'], set()).add(
                        make_entry(group))
                # ...while accounts require extra processing
                elif member['member_type'] == co.entity_account:
                    account_ids.append(member['member_id'])
            # Map account IDs to person IDs
            for person_id in account_ids_to_person_ids(account_ids):
                persons.setdefault(person_id, set()).add(make_entry(group))
        return persons


class FeideServiceAuthnLevelMixin(Entity_class):
    """ Mixin class for entity authentication levels. """

    def delete(self):
        """ Deletes all authentication levels associated with this entity. """
        if self.entity_id:
            for authn in self.search_authn_level(entity_id=self.entity_id):
                self.remove_authn_level(**authn)
        self.__super.delete()

    def add_authn_level(self, service_id, level, entity_id=None):
        """ Add an authentication level. """
        if entity_id is None:
            entity_id = self.entity_id
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=feide_service_authn_level]
          (service_id, entity_id, level)
        VALUES (:service_id, :entity_id, :level)""",
                     {'service_id': service_id,
                      'entity_id': entity_id,
                      'level': level})
        self._db.log_change(
            entity_id,
            self.clconst.feide_service_authn_level_add,
            service_id,
            change_params={'level': level})

    def remove_authn_level(self, service_id, level, entity_id=None):
        """ Remove an authentication level. """
        if entity_id is None:
            entity_id = self.entity_id
        binds = {'service_id': service_id,
                 'entity_id': entity_id,
                 'level': level}
        exists_stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=feide_service_authn_level]
            WHERE service_id=:service_id AND
                  entity_id=:entity_id AND
                  level=:level
          )
        """
        if not self.query_1(exists_stmt, binds):
            # False positive
            return
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=feide_service_authn_level]
          WHERE service_id=:service_id AND
                entity_id=:entity_id AND
                level=:level
        """
        self.execute(delete_stmt, binds)
        self._db.log_change(entity_id,
                            self.clconst.feide_service_authn_level_del,
                            service_id,
                            change_params={'level': level})

    def search_authn_level(self, service_id=None, entity_id=None, level=None):
        """ Search authentication levels. """
        tables = [
            "[:table schema=cerebrum name=feide_service_authn_level] fsal"]
        where = []
        if service_id is not None:
            where.append("fsal.service_id=:service_id")
        if entity_id is not None:
            where.append("fsal.entity_id=:entity_id")
        if level is not None:
            where.append("fsal.level=:level")
        where_str = "WHERE " + " AND ".join(where) if where else ""
        binds = {'service_id': service_id,
                 'entity_id': entity_id,
                 'level': level}
        return self.query("""
        SELECT DISTINCT fsal.service_id AS service_id,
                        fsal.entity_id AS entity_id,
                        fsal.level AS level
        FROM %s %s""" % (','.join(tables), where_str), binds)
