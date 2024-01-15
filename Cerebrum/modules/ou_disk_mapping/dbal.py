# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
Database access for the ``mod_ou_disk_mapping`` tables.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Disk import Disk
from Cerebrum.Utils import Factory, NotSet, argument_to_sql

from .constants import CLConstants


# Columns and column order for selects
DEFAULT_FIELDS = ('ou_id', 'aff_code', 'status_code', 'disk_id')

# Result row ordering in queries
DEFAULT_ORDER = ('ou_id', 'disk_id', 'aff_code', 'status_code')


class OUDiskMapping(DatabaseAccessor):
    """ Database access to the default disk rules. """

    def __init__(self, database):
        super(OUDiskMapping, self).__init__(database)
        self.disk = Disk(self._db)
        self.const = Factory.get('Constants')(self._db)

    def __insert(self, ou_id, aff_code, status_code, disk_id):
        """
        Insert a new row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou

        :type aff_code: None, Cerebrum.Constants._PersonAffiliationCode
        :param aff_code: Cerebrum person aff constant

        :type status_code: None, Cerebrum.Constants._PersonAffStatusCode
        :param status_code: Cerebrum person aff status constant

        :param int or None disk_id: entity_id of the disk
        """
        binds = {
            'ou_id': int(ou_id),
            'aff_code': (None if aff_code is None else int(aff_code)),
            'status_code': (None if status_code is None else int(status_code)),
            'disk_id': int(disk_id),
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=ou_disk_mapping]
            (ou_id, aff_code, status_code, disk_id)
          VALUES
            (:ou_id, :aff_code, :status_code, :disk_id)
        """
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(int(disk_id))
        self._db.log_change(
            int(ou_id),
            CLConstants.ou_disk_add,
            None,
            change_params={
                'aff': (six.text_type(status_code) if status_code
                        else six.text_type(aff_code)),
                'path': six.text_type(self.disk.path),
            }
        )

    def __update(self, ou_id, aff_code, status_code, disk_id):
        """
        Update a row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int disk_id: entity_id of the disk
        """
        binds = {
            'ou_id': int(ou_id),
            'disk_id': int(disk_id),
        }
        where = "ou_id = :ou_id"
        if aff_code is None:
            where += " AND aff_code IS NULL"
        else:
            where += " AND aff_code = :aff_code"
            binds['aff_code'] = int(aff_code)

        if status_code is None:
            where += " AND status_code IS NULL"
        else:
            where += " AND status_code = :status_code"
            binds['status_code'] = int(status_code)

        stmt = """
          UPDATE [:table schema=cerebrum name=ou_disk_mapping]
          SET
            disk_id = :disk_id
          WHERE {where}
        """.format(where=where)
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(int(disk_id))
        self._db.log_change(
            int(ou_id),
            CLConstants.ou_disk_add,
            None,
            change_params={
                'aff': (six.text_type(status_code) if status_code
                        else six.text_type(aff_code)),
                'path': six.text_type(self.disk.path),
            }
        )

    def delete(self, ou_id, aff_code, status_code):
        """
        Delete disk_id for a given ou_id and aff_code

        :param int ou_id: entity_id of the ou

        :type aff_code: None, Cerebrum.Constants._PersonAffiliationCode
        :param aff_code: Cerebrum person aff constant

        :type status_code: None, Cerebrum.Constants._PersonAffStatusCode
        :param status_code: Cerebrum person aff status constant
        """
        try:
            old_values = self.get(ou_id, aff_code, status_code)
        except Errors.NotFoundError:
            # Nothing to remove
            return
        disk_id = old_values['disk_id']

        binds = {
            'ou_id': int(ou_id),
        }

        where = "ou_id = :ou_id"
        if aff_code is None:
            where += " AND aff_code IS NULL AND status_code IS NULL"
        else:
            where += " AND aff_code = :aff_code"
            binds['aff_code'] = int(aff_code)
            if status_code is None:
                where += " AND status_code IS NULL"
            else:
                where += " AND status_code = :status_code"
                binds['status_code'] = int(status_code)

        stmt = """
          DELETE FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE {where}
        """.format(where=where)
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(int(disk_id))
        self._db.log_change(
            int(ou_id),
            CLConstants.ou_disk_remove,
            None,
            change_params={
                'aff': (six.text_type(status_code) if status_code
                        else six.text_type(aff_code)),
                'path': six.text_type(self.disk.path)
            }
        )

    def get(self, ou_id, aff_code, status_code):
        """
        Get values for a given combination of ou, aff, status

        :param int ou_id: entity_id of the ou

        :type aff_code: None, Cerebrum.Constants._PersonAffiliationCode
        :param aff_code: Cerebrum person aff constant

        :type status_code: None, Cerebrum.Constants._PersonAffStatusCode
        :param status_code: Cerebrum person aff status constant

        :rtype: db.row
        :return: ou_id, aff_code, status_code, disk_id
        """
        binds = {'ou_id': int(ou_id)}
        conds = ["ou_id = :ou_id"]

        if aff_code is None:
            conds.extend(("aff_code IS NULL", "status_code IS NULL"))
        else:
            conds.append("aff_code = :aff_code")
            binds['aff_code'] = int(aff_code)
            if status_code is None:
                conds.append("status_code IS NULL")
            else:
                conds.append("status_code = :status_code")
                binds['status_code'] = int(status_code)

        stmt = """
          SELECT {fields}
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE {conds}
        """.format(
            fields=', '.join(DEFAULT_FIELDS),
            conds=" AND ".join(conds),
        )
        return self.query_1(stmt, binds)

    def add(self, ou_id, aff_code, status_code, disk_id):
        """
        Set disk_id for a given combination of ou and affiliation

        :param int ou_id: entity_id of the ou

        :type aff_code: None, Cerebrum.Constants._PersonAffiliationCode
        :param aff_code: Cerebrum person aff constant

        :type status_code: None, Cerebrum.Constants._PersonAffStatusCode
        :param status_code: Cerebrum person aff status constant

        :param int disk_id: entity_id of the disk
        """

        # Check old values
        try:
            old_values = self.get(ou_id, aff_code, status_code)
        except Errors.NotFoundError:
            is_new = True
        else:
            is_new = False
            # Check if anything is new
            if old_values['disk_id'] == disk_id:
                return

        # Insert new values
        if is_new:
            self.__insert(ou_id, aff_code, status_code, disk_id)
        else:
            self.__update(ou_id, aff_code, status_code, disk_id)

    def search(self, ou_id=None, disk_id=None,
               affiliation=NotSet, status=NotSet,
               limit=None):
        """
        Search for disk mapping rules.

        :param int ou_id: Filter results by one or more ou ids
        :param int disk_id: Filter results by one or more disk ids
        :param affiliation: Filter results by affiliation
        :param status: Filter results by affiliation status

        .. note::
           *affiliation* and affiliation *status* takes `None` to mean
           *no value in rule* - i.e. a rule that matches all values.  Use the
           default `NotSet` to avoid filtering on affiliation or affiliation
           status.

        :returns:
            Rows of (ou_id, aff_code, status_code, disk_id) disk mapping rules.
        """
        conds = []
        binds = {}

        if ou_id is not None:
            conds.append(argument_to_sql(ou_id, 'ou_id', binds, int))

        if disk_id is not None:
            conds.append(argument_to_sql(disk_id, 'disk_id', binds, int))

        if affiliation is None:
            conds.append("aff_code IS NULL")
        elif affiliation:
            conds.append("aff_code = :aff_code")
            binds['aff_code'] = int(affiliation)

        if status is None:
            conds.append("status_code IS NULL")
        elif status:
            conds.append("status_code = :status_code")
            binds['status_code'] = int(status)

        if limit is None:
            limit_clause = ''
        else:
            limit_clause = 'LIMIT :limit'
            binds['limit'] = int(limit)

        stmt = """
          SELECT {fields}
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          {where}
          ORDER BY {order}
          {limit}
        """.format(
            fields=', '.join(DEFAULT_FIELDS),
            limit=limit_clause,
            order=', '.join(DEFAULT_ORDER),
            where=("WHERE " + " AND ".join(conds)) if conds else "",
        )

        return self.query(stmt, binds)
