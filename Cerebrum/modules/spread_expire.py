# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
Implementation of mod_spread_expire

This module adds expire_date to entity spreads, and a notification feature to
inform users that gets a spread revoked.
"""
import logging

import mx.DateTime
import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import argument_to_sql

logger = logging.getLogger(__name__)


class SpreadExpire(DatabaseAccessor):
    """
    Access to the spread_expire table.

    TODO: We assume a (entity_id, spread) primary key, but no such constraint
    exists in the database - this may fail horribly if anything else modifies
    that table.
    """

    def __insert(self, entity_id, spread, expire_date):
        """
        Insert a new row in the spread_expire table.
        """
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
            'expire_date': expire_date,
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=spread_expire]
            (entity_id, spread, expire_date)
          VALUES
            (:entity_id, :spread, :expire_date)
        """
        logger.debug('inserting spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def __update(self, entity_id, spread, expire_date):
        """
        Update an existing row in the spread_expire table.
        """
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
            'expire_date': expire_date,
        }
        stmt = """
          UPDATE [:table schema=cerebrum name=spread_expire]
          SET expire_date = :expire_date
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        logger.debug('updating spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def exists(self, entity_id, spread):
        """
        Check if there is an expire date for a given spread on a given entity.

        :type entity_id: int
        :type spread: Cerebrum.Constants._SpreadCode
        """
        if not entity_id or not spread:
            raise ValueError("missing args")
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=spread_expire]
            WHERE
              entity_id = :entity_id AND
              spread = :spread
          )
        """
        return self.query_1(stmt, binds)

    def get(self, entity_id, spread):
        """
        Get an expire date for a given spread on a given entity.

        :type entity_id: int
        :type spread: Cerebrum.Constants._SpreadCode
        """
        if not entity_id or not spread:
            raise ValueError("missing args")
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          SELECT expire_date
          FROM [:table schema=cerebrum name=spread_expire]
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        return self.query_1(stmt, binds)

    def set(self, entity_id, spread, expire_date):
        """
        Add or update a spread expire date.

        :type entity_id: int
        :type spread: Cerebrum.Constants._SpreadCode
        :type expire_date: mx.DateTime.DateTime, datetime.date
        """
        try:
            old_date = self.get(entity_id, spread)
            is_new = False
        except Errors.NotFoundError:
            old_date = None
            is_new = True

        if not is_new and old_date == expire_date:
            logger.debug(
                'No change in spread_expire for entity_id=%r spread=%r',
                entity_id, spread)
            return

        if is_new:
            self.__insert(entity_id, spread, expire_date)
        else:
            self.__update(entity_id, spread, expire_date)

    def delete(self, entity_id, spread):
        """
        Delete a spread expire date.

        :type entity_id: int
        :type spread: Cerebrum.Constants._SpreadCode
        """
        if not self.exists(entity_id, spread):
            return

        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          DELETE FROM
            [:table schema=cerebrum name=spread_expire]
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        logger.debug('Deleting spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def search(self, entity_id=None, spread=None, before_date=None,
               after_date=None, fetchall=False):
        """
        Search for spread expire dates.

        :param entity_id:
            Filter results by a single entity_id or a sequence of entity_id
            values.

        :param spread:
            Filter results by a single spread or a sequence of spread values.

        :param before_date:
            Only include results with an expire_date older than this date.

        :param after_date:
            Only include results with an expire_date newer than this date.
        """
        filters = []
        binds = dict()

        if entity_id:
            filters.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))
        if spread:
            filters.append(
                argument_to_sql(spread, 'spread', binds, int))

        if before_date is not None:
            binds['before_date'] = before_date
            filters.append('expire_date < :before_date')

        if after_date is not None:
            binds['after_date'] = before_date
            filters.append('expire_date > :after_date')

        where = ('WHERE ' + ' AND '.join(filters)) if filters else ''

        stmt = """
          SELECT entity_id, spread, expire_date
          FROM [:table schema=cerebrum name=spread_expire]
          {where}
        """.format(where=where)
        return self.query(stmt, binds)


class EntitySpreadMixin(EntitySpread):
    """
    Mixin class that will extend EntitySpread funcionality.
    """

    def __init__(self, database):
        super(EntitySpreadMixin, self).__init__(database)
        self._spread_expire_db = SpreadExpire(database)

    def delete(self):
        """Delete an entity's spreads."""
        for s in self.get_spread():
            self.delete_spread(s['spread'])
        super(EntitySpreadMixin, self).delete()

    def add_spread(self, spread):
        """Add ``spread`` to this entity."""
        self.set_spread_expire(int(spread))
        super(EntitySpreadMixin, self).add_spread(spread)

    def delete_spread(self, spread):
        """Remove ``spread`` from this entity."""
        self._spread_expire_db.delete(self.entity_id, spread)
        super(EntitySpreadMixin, self).delete_spread(spread)

    def set_spread_expire(self, spread, expire_date=None, entity_id=None):
        """
        Set expire date for a given spread.
        """

        if entity_id is None:
            entity_id = self.entity_id

        if expire_date is None:
            expire_date = mx.DateTime.today()
        self._spread_expire_db.set(entity_id, spread, expire_date)

    def search_spread_expire(self, spread=None, expire_date=None,
                             entity_id=None):
        return list(
            self._spread_expire_db.search(
                entity_id=entity_id,
                spread=spread,
                after_date=expire_date,
            ))
