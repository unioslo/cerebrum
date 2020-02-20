# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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


class GroupMemberships(DatabaseAccessor):
    """Provide methods related to group memberships."""

    def __init__(self, database):
        self.const = Factory.get('Constants')(database)
        super(GroupMemberships, self).__init__(database)

    def get_groups(self,
                   member_id,
                   group_spread=None,
                   group_type=None,
                   filter_expired=True,
                   max_recursion_depth=20):
        """
        Get group membership for one or multiple entities.

        :param member_id: Member id to look for.
        :type member_id: int or sequence of int

        :param group_spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.
        :type group_spread: int, SpreadCode, sequence thereof or None.

        :param group_type:
          Filter the resulting group list by group type. I.e only groups with
          the specified types(s) will be returned.
        :type group_type: int, EntityType constant, a sequence thereof or None.

        :param filter_expired:
          Filter the resulting group list by expiration date. If set, do NOT
          return groups that have expired (i.e. have group_info.expire_date in
          the past relative to the call time).
        :type filter_expired: boolean

        :param max_recursion_depth: int
        :type max_recursion_depth: Maximum depth of iterations

        :return: Group membership info for member_id.
        :rtype: iterable (yielding db-rows with group membership information)
        """
        binds = {
            "max_level": max_recursion_depth,
            "value_domain": int(self.const.group_namespace),
            "entity_type": int(self.const.entity_group),
        }
        select = [
            'ms.group_id as group_id',
            'en.entity_name AS name',
            'gi.description AS description',
            'gi.visibility AS visibility',
            'gi.creator_id AS creator_id',
            'ei.created_at AS created_at',
            'gi.expire_date AS expire_date',
            'gi.group_type AS group_type'
        ]
        extra_joins = []
        where = []

        member_where = argument_to_sql(member_id, "gm.member_id", binds, int)

        if filter_expired:
            where.append("(gi.expire_date IS NULL OR gi.expire_date > [:now])")

        if group_spread is not None:
            extra_joins.append(
                """
                LEFT JOIN [:table schema=cerebrum name=entity_spread] es
                  on ga.group_id = es.entity_id"
                """)
            where.append(
                argument_to_sql(group_spread, "es.spread", binds, int))

        if group_type is not None:
            where.append(
                argument_to_sql(group_type, "gi.group_type", binds, int))

        query_str = """
        WITH RECURSIVE member_search(group_id, member_id, level) AS (
          SELECT
            gm.group_id,
            gm.member_id,
            1 as level
          FROM [:table schema=cerebrum name=group_member] gm
          WHERE
            {member_where}
          UNION ALL
          SELECT
            gm.group_id,
            member_search.member_id,
            level + 1
          FROM [:table schema=cerebrum name=group_member] gm
          JOIN member_search
          ON gm.member_id = member_search.group_id
          where level < :max_level
        )
        SELECT DISTINCT
          {select}
        FROM member_search ms
        LEFT JOIN [:table schema=cerebrum name=entity_name] en
          ON en.entity_id = ms.group_id AND
             en.value_domain = :value_domain
        LEFT JOIN [:table schema=cerebrum name=group_info] gi
          ON gi.group_id = ms.group_id
        LEFT JOIN [:table schema=cerebrum name=entity_info] ei
          ON ei.entity_id = ms.group_id AND
             ei.entity_type = :entity_type
        {extra_joins}
        WHERE {where}
        """.format(
            member_where=member_where,
            extra_joins='\n'.join(extra_joins) if extra_joins else '',
            select=', '.join(select),
            where=' AND '.join(where) if where else ''
        )

        return self.query(query_str, binds)

    def get_members(self, group_id):
        """
        Get _all_ members of a group.

        :param group_id: Group (id)
        :type group_id: int or sequence of int
        """
        raise NotImplementedError
