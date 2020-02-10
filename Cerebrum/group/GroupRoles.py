# -*- coding: utf-8 -*-
# Copyright 2019 University of Oslo, Norway
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

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import argument_to_sql, Factory


class GroupRoles(DatabaseAccessor):
    """
    Provide methods related to privileged users of a group.
    This is admins and moderators. Information about these exists in the
    group_admin and group_moderator tables.
    """

    def __init__(self, database):
        self.clconst = Factory.get('CLConstants')(database)
        super(GroupRoles, self).__init__(database)

    def add_admin_to_group(self, admin_id, group_id):
        """Add L{admin_id} as admin of the group L{group_id}.

        :param int admin_id:
          Admin (id) to add to the group. This should be an account or a group
        :param int group_id:
          Group (id) to add the admin to
        """
        stmt = """
        INSERT INTO [:table schema=cerebrum name=group_admin]
          (group_id, admin_id)
        VALUES
          (:group_id, :admin_id)
        """
        binds = {'group_id': int(group_id),
                 'admin_id': int(admin_id)}
        self.execute(stmt, binds)
        self._db.log_change(group_id,
                            self.clconst.group_admin_add,
                            admin_id)

    def add_moderator_to_group(self, moderator_id, group_id):
        """Add L{moderator_id} as moderator of the group L{group_id}.

        :param int moderator_id:
          Moderator (id) to add to the group. This should be an account or a
          group
        :param int group_id:
          Group (id) to add the moderator to
        """
        stmt = """
        INSERT INTO [:table schema=cerebrum name=group_moderator]
          (group_id, moderator_id)
        VALUES
          (:group_id, :moderator_id)
        """
        binds = {'group_id': int(group_id),
                 'moderator_id': int(moderator_id)}
        self.execute(stmt, binds)
        self._db.log_change(group_id,
                            self.clconst.group_moderator_add,
                            moderator_id)

    def remove_admin_from_group(self, admin_id, group_id):
        """Remove L{admin_id}'s adminship from a group.

        :param int admin_id:
          Admin (id) to remove from group.

        :param int group_id:
            Group (id) to remove admin from
        """
        if not self.is_admin(admin_id, group_id):
            return False

        binds = {'group_id': group_id,
                 'admin_id': admin_id}
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=group_admin]
            WHERE group_id=:group_id AND
            admin_id=:admin_id"""
        self.execute(delete_stmt, binds)
        self._db.log_change(group_id,
                            self.clconst.group_admin_rem,
                            admin_id)
        return True

    def remove_moderator_from_group(self, moderator_id, group_id):
        """Remove L{moderator_id}'s moderatorship from a group.

        :param int moderator_id:
          Moderator (id) to remove from group.

        :param int group_id:
            Group (id) to remove moderator from
        """
        if not self.is_moderator(moderator_id, group_id):
            return False

        binds = {'group_id': group_id,
                 'moderator_id': moderator_id}
        delete_stmt = """
          DELETE FROM [:table schema=cerebrum name=group_moderator]
            WHERE group_id=:group_id AND
            moderator_id=:moderator_id"""
        self.execute(delete_stmt, binds)
        self._db.log_change(group_id,
                            self.clconst.group_moderator_rem,
                            moderator_id)
        return True

    def remove_all(self, group_id):
        """Remove all admins and managers from to the group

        :param int group_id:
            Group (id) to remove admins and managers from
        """
        binds = {'group_id': group_id}

        # Find admins and log removals
        admins = self.query("""
        SELECT admin_id FROM [:table schema=cerebrum name=group_admin]
        WHERE group_id=:group_id""", binds)
        for admin in admins:
            self._db.log_change(group_id,
                                self.clconst.group_admin_rem,
                                admin['admin_id'])
        # Remove them
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=group_admin]
        WHERE group_id=:group_id""", binds)

        # Find mods and log removals
        mods = self.query("""
        SELECT moderator_id FROM [:table schema=cerebrum name=group_moderator]
        WHERE group_id=:group_id""", binds)
        for mod in mods:
            self._db.log_change(group_id,
                                self.clconst.group_moderator_rem,
                                mod['moderator_id'])
        # Remove them
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=group_moderator]
        WHERE group_id=:group_id""", binds)

    def search_admins(self, group_id=None, group_spread=None, group_type=None,
                      admin_id=None, admin_type=None,
                      include_group_name=False):
        """Search for group *ADMINS* satisfying certain criteria.

        If a filter is None, it means that it will not be applied. Calling
        this method without any argument will return all admins of groups

        All filters except for L{group_id} and L{group_spread} are applied to
        admins, rather than groups containing admins.

        The db-rows eventually returned by this method contain these keys:
        group_id, admin_type, admin_id, as well as group_name if wanted

        :type group_id: int or a sequence thereof or None.
        :param group_id:
          Group ids to look for. Given a group_id, only adminships in the
          specified groups will be returned. This is useful for answering
          questions like 'give a list of all admins of group <foo>'.

        :type spread: int or SpreadCode or sequence thereof or None.
        :param spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.

        :type admin_id: int or a sequence thereof or None.
        :param admin_id:
          The result adminship list will be filtered by admin_ids -
          only the specified admin_ids will be listed. This is useful for
          answering questions like 'give a list of adminships held by
          <entity_id>'.

        :type admin_type:
          int or an EntityType constant or a sequence thereof or None.
        :param admin_type:
          The resulting adminship list be filtered by admin type -
          only the admin entities of the specified type will be returned.
          This is useful for answering questions like 'give me a list of
          *group* admins of group <bla>'.

        :type include_group_name: boolean
        :param include_group_name:
          The resulting rows will include the name of the group in addition to
          the id.

        :rtype: generator (yielding db-rows with adminship information)
        :return:
          A generator that yields successive db-rows (from group_admin)
          matching all of the specified filters. These keys are available in
          each of the db_rows:
            - group_id
            - admin_id
            - admin_type
           (- group_name)
        """
        select = ["ga.group_id AS group_id",
                  "ga.admin_id AS admin_id",
                  "ei.entity_type AS admin_type"]
        tables = ["[:table schema=cerebrum name=group_admin] ga",
                  "[:table schema=cerebrum name=entity_info] ei"]
        where = ["ga.admin_id = ei.entity_id"]
        binds = {}

        if group_id is not None:
            where.append(
                argument_to_sql(
                    group_id, "ga.group_id", binds, int))

        if group_spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("ga.group_id = es.entity_id")
            where.append(
                argument_to_sql(
                    group_spread, "es.spread", binds, int))

        if admin_id is not None:
            where.append(
                argument_to_sql(
                    admin_id, "ga.admin_id", binds, int))

        if admin_type is not None:
            where.append(
                argument_to_sql(
                    admin_type, "ei.entity_type", binds, int))

        if group_type is not None:
            tables.append("[:table schema=cerebrum name=group_info] gi")
            where.append("gi.group_id = ga.group_id")
            where.append(
                argument_to_sql(
                    group_type, "gi.group_type", binds, int))

        if include_group_name:
            tables.append("[:table schema=cerebrum name=entity_name] en")
            where.append("ga.group_id = en.entity_id")
            select.append("en.entity_name AS group_name")

        query = """
        SELECT {select}
        FROM {tables}
        WHERE {where}
        """.format(select=", ".join(select),
                   tables=", ".join(tables),
                   where=" AND ".join(where))

        return self.query(query, binds)

    def search_moderators(self, group_id=None, group_spread=None,
                          moderator_id=None, moderator_type=None,
                          include_group_name=False):
        """Search for group *MODERATORS* satisfying certain criteria.

        If a filter is None, it means that it will not be applied. Calling
        this method without any argument will return all moderators of groups

        All filters except for L{group_id} and L{group_spread} are applied to
        moderators, rather than groups containing moderators.

        The db-rows eventually returned by this method contain these keys:
        group_id, moderator_type, moderator_id, as well as group_name if wanted

        :type group_id: int or a sequence thereof or None.
        :param group_id:
          Group ids to look for. Given a group_id, only moderatorships in the
          specified groups will be returned. This is useful for answering
          questions like 'give a list of all moderators of group <foo>'.

        :type spread: int or SpreadCode or sequence thereof or None.
        :param spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.

        :type moderator_id: int or a sequence thereof or None.
        :param moderator_id:
          The result moderatorship list will be filtered by moderator_ids -
          only the specified moderator_ids will be listed. This is useful for
          answering questions like 'give a list of moderatorships held by
          <entity_id>'.

        :type moderator_type:
          int or an EntityType constant or a sequence thereof or None.
        :param moderator_type:
          The resulting moderatorship list be filtered by moderator type -
          only the moderator entities of the specified type will be returned.
          This is useful for answering questions like 'give me a list of
          *group* moderators of group <bla>'.

        :type include_group_name: boolean
        :param include_group_name:
          The resulting rows will include the name of the group in addition to
          the id.

        :rtype: generator (yielding db-rows with moderatorship information)
        :return:
          A generator that yields successive db-rows (from group_moderator)
          matching all of the specified filters. These keys are available in
          each of the db_rows:
            - group_id
            - moderator_id
            - moderator_type
           (- group_name)
        """
        select = ["gm.group_id AS group_id",
                  "gm.moderator_id AS moderator_id",
                  "ei.entity_type AS moderator_type"]
        tables = ["[:table schema=cerebrum name=group_moderator] gm",
                  "[:table schema=cerebrum name=entity_info] ei"]
        where = ["gm.moderator_id = ei.entity_id"]
        binds = {}

        if group_id is not None:
            where.append(
                argument_to_sql(
                    group_id, "gm.group_id", binds, int))

        if group_spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("gm.group_id = es.entity_id")
            where.append(
                argument_to_sql(
                    group_spread, "es.spread", binds, int))

        if moderator_id is not None:
            where.append(
                argument_to_sql(
                    moderator_id, "gm.moderator_id", binds, int))

        if moderator_type is not None:
            where.append(
                argument_to_sql(
                    moderator_type, "ei.entity_type", binds, int))

        if include_group_name:
            tables.append("[:table schema=cerebrum name=entity_name] en")
            where.append("gm.group_id = en.entity_id")
            select.append("en.entity_name AS group_name")

        query = """
        SELECT {select}
        FROM {tables}
        WHERE {where}
        """.format(select=", ".join(select),
                   tables=", ".join(tables),
                   where=" AND ".join(where))

        return self.query(query, binds)

    def is_admin(self, admin_id, group_id=None):
        """
        Function to determine wheter an Entity is an admin of a group in
        general, or of one particular group, if specified. Either directly or
        through membership in an admin group

        :param int admin_id:
          Entity id to look after adminship for

        :param int group_id:
          If specified, the adminship needs to be for this particular group

        :return bool:
          Whether the entity is an admin (of the specified group)
        """
        binds = {}
        where = []
        where.append(argument_to_sql(admin_id, "admin_id", binds, int))
        if group_id is not None:
            where.append(argument_to_sql(group_id, "group_id", binds, int))

        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=group_admin]
          WHERE {where}
        )
        """.format(where=" AND ".join(where))
        return self.query_1(exists_stmt, binds)

    def is_moderator(self, moderator_id, group_id=None):
        """
        Function to determine wheter an Entity is an moderator of a group in
        general, or of one particular group, if specified. Either directly or
        through membership in a moderator group

        :param int moderator_id:
          Entity id to look after moderatorship for

        :param int group_id:
          If specified, the moderatorship needs to be for this particular group

        :return bool:
          Whether the entity is an moderator (of the specified group)
        """
        binds = {}
        where = []
        where.append(argument_to_sql(moderator_id, "moderator_id", binds, int))
        if group_id is not None:
            where.append(argument_to_sql(group_id, "group_id", binds, int))

        exists_stmt = """
        SELECT EXISTS (
          SELECT 1
          FROM [:table schema=cerebrum name=group_moderator]
          WHERE {where}
        )
        """.format(where=" AND ".join(where))
        return self.query_1(exists_stmt, binds)
