# -*- coding: utf-8 -*-
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
Implementation of mod_stillingskoder.

The stillingskoder module provides a list of known employment codes
(stillingskode, sko) along with an associated title and category.

History
-------
This functionality was previously implemented through SQL queries in
contrib/no/uit/import_stillingskoder.py, as well as queries in some exports.

The old implementation can be seen in:

    commit 1d3a97e41c24ff6cf1b362fc6242f103a9bb8274
    Date:   Tue May 21 16:09:15 2019 +0200
"""
import logging

import six

from Cerebrum import DatabaseAccessor
from Cerebrum import Errors
from Cerebrum.Utils import argument_to_sql, prepare_string

__version__ = '1.0'

logger = logging.getLogger(__name__)


class Stillingskoder(DatabaseAccessor.DatabaseAccessor):
    """ DBAL for person_stillingskoder. """

    def exists(self, code):
        """
        Check if a given employment code exists.

        :type code: int

        :rtype: bool
        """
        binds = {'stillingskode': int(code)}
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=person_stillingskoder]
            WHERE
              stillingskode = :stillingskode
          )
        """
        return self.query_1(stmt, binds)

    def get(self, code):
        """
        Get metadata for a given employment code.

        :type code: int

        :returns:
            A dict-like object with keys ('code', 'title', 'category')

        :raises: NotFoundError
        """
        binds = {'stillingskode': int(code)}
        stmt = """
          SELECT
            stillingskode as code,
            stillingstittel as title,
            stillingstype as category
          FROM [:table schema=cerebrum name=person_stillingskoder]
          WHERE stillingskode = :stillingskode
        """
        return self.query_1(stmt, binds)

    def set(self, code, title, category):
        """
        Set metadata for a given employment code.

        :type code: int
        :type title: str
        :type category: str
        """
        try:
            old = self.get(code)
            is_new = False
        except Errors.NotFoundError:
            old = {}
            is_new = True

        if (not is_new and
                title == old['title'] and
                category == old['category']):
            logger.debug("no change in employment code=%r", code)
            return

        binds = {
            'stillingskode': int(code),
            'stillingstittel': six.text_type(title),
            'stillingstype': six.text_type(category),
        }

        if is_new:
            stmt = """
              INSERT INTO [:table schema=cerebrum name=person_stillingskoder]
                  (stillingskode, stillingstittel, stillingstype)
              VALUES
                  (:stillingskode, :stillingstittel, :stillingstype)
            """
            logger.debug('inserting employment code=%r', code)
        else:
            stmt = """
              UPDATE [:table schema=cerebrum name=person_stillingskoder]
              SET
                stillingstittel = :stillingstittel,
                stillingstype = :stillingstype
              WHERE stillingskode = :stillingskode
            """
            logger.debug('updating employment code=%r', code)
        self.execute(stmt, binds)
        return is_new

    def delete(self, code):
        """
        Remove a given employment code.

        :type code: int

        :raises: NotFoundError
        """
        if not self.exists(code):
            raise Errors.NotFoundError("No employment code=%r" % (code, ))

        binds = {'stillingskode': int(code)}
        stmt = """
          DELETE FROM [:table schema=cerebrum name=person_stillingskoder]
          WHERE stillingskode = :stillingskode
        """
        logger.debug("removing employment code=%r", code)
        return self.execute(stmt, binds)

    def search(self, code=None, title=None, category=None, fetchall=True):
        """
        List employment codes.

        :param code:
            An optional employment code (int) to filter by. Also accepts a
            sequence of acceptable employment codes.
        :param title:
            An optional employment title pattern to filter by.
        :param category:
            An optional employment category pattern to filter by.
        :param fetchall:
            If true, return a list of results (rows), if false, return an
            iterator.

        :return:
            A list or iterator with results.  Each result is a dict-like object
            with keys ('code', 'title', 'category').
        """
        binds = {}
        filters = []

        if code is not None:
            filters.append(argument_to_sql(code, 'stillingskode', binds, int))
        if title is not None:
            filters.append('stillingstittel like :stillingstittel')
            binds['stillingstittel'] = prepare_string(title)
        if category is not None:
            filters.append('stillingstype like :stillingstype')
            binds['stillingstype'] = prepare_string(category)

        stmt = """
          SELECT
            stillingskode as code,
            stillingstittel as title,
            stillingstype as category
          FROM [:table schema=cerebrum name=person_stillingskoder]
          {where}
        """.format(where=('WHERE ' + ' AND '.join(filters)) if filters else '')
        return self.query(stmt, binds, fetchall=fetchall)
