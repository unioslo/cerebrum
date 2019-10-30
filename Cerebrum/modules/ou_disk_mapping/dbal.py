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
"""
Implementation of mod_ou_disk_mapping database access.
"""
import six

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Disk import Disk
from Cerebrum.Utils import NotSet, Factory
from .constants import CLConstants
from .utils import aff_lookup


class OUDiskMapping(DatabaseAccessor):
    """
    Map OU and Affiliation to Disk
    """
    def __init__(self, database):
        super(OUDiskMapping, self).__init__(database)
        self.disk = Disk(self._db)
        self.const = Factory.get('Constants')(self._db)

    def __insert(self, ou_id, aff_code, disk_id):
        """
        Insert a new row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou
        :param int or None aff_code: int of affiliation constant
        :param int or None disk_id: entity_id of the disk
        """
        if aff_code is None:
            status_code = None
        else:
            aff_code, status_code = aff_lookup(self.const, int(aff_code))
        binds = {
            'ou_id': int(ou_id),
            'aff_code': aff_code if aff_code is None else int(aff_code),
            'status_code': status_code if status_code is None else int(
                status_code),
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
                'aff': six.text_type(
                    status_code) if status_code else six.text_type(aff_code),
                'path': six.text_type(self.disk.path),
            }
        )

    def __update(self, ou_id, aff_code, disk_id):
        """
        Update a row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int disk_id: entity_id of the disk
        """
        if aff_code is None:
            status_code = None
        else:
            aff_code, status_code = aff_lookup(self.const, int(aff_code))

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
                'aff': six.text_type(
                    status_code) if status_code else six.text_type(aff_code),
                'path': six.text_type(self.disk.path),
            }
        )

    def delete(self, ou_id, aff_code):
        """
        Delete disk_id for a given ou_id and aff_code

        :param int ou_id: entity_id of the ou
        :param int or None aff_code: int of affiliation constant
        """
        try:
            old_values = self.get(ou_id, aff_code)
        except Errors.NotFoundError:
            # Nothing to remove
            return
        disk_id = old_values['disk_id']
        aff_code = old_values['aff_code']
        status_code = old_values['status_code']

        binds = {
            'ou_id': int(ou_id),
        }

        where = "ou_id = :ou_id"
        if aff_code is None:
            where += " AND aff_code IS NULL AND status_code IS NULL"
        else:
            where += " AND aff_code = :aff_code"
            binds['aff_code'] = int(aff_code)
            if status_code is not None:
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
                'aff': six.text_type(
                    status_code) if status_code else six.text_type(aff_code),
                'path': six.text_type(self.disk.path)
            }
        )

    def get_with_disk(self, disk_id):
        """
        Get all OUs and Affiliations that use a disk_id

        :param int disk_id:
        :return: list of db.rows with keys ou_id, aff_code, disk_id
        """
        binds = {
            'disk_id': int(disk_id),
        }
        stmt = """
          SELECT ou_id, aff_code, status_code
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE
            disk_id = :disk_id
        """
        return self.query(stmt, binds)

    def get(self, ou_id, aff_code):
        """
        Get values for a given combination of ou, aff, status

        :param int ou_id: entity_id of the ou

        :type aff_code: int, None
        :param aff_code: Cerebrum person aff (status) constant

        :rtype: db.row
        :return: ou_id, aff_code, status_code, disk_id
        """
        binds = {
            'ou_id': int(ou_id),
        }

        where = "ou_id = :ou_id"
        if aff_code is None:
            where += " AND aff_code IS NULL AND status_code IS NULL"
        else:
            aff_code, status_code = aff_lookup(self.const, int(aff_code))
            where += " AND aff_code = :aff_code"
            binds['aff_code'] = int(aff_code)
            if status_code is not None:
                where += " AND status_code = :status_code"
                binds['status_code'] = int(status_code)

        stmt = """
          SELECT ou_id, aff_code, status_code, disk_id
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE {where}
        """.format(where=where)
        return self.query_1(stmt, binds)

    def add(self, ou_id, aff_code, disk_id):
        """
        Set disk_id for a given combination of ou and affiliation

        :param int ou_id: entity_id of the ou
        :param int or None aff_code: int of affiliation constant
        :param int disk_id: entity_id of the disk
        """
        # Check old values
        try:
            old_values = self.get(ou_id, aff_code)
        except Errors.NotFoundError:
            is_new = True
        else:
            is_new = False
            # Check if anything is new
            if old_values['disk_id'] == disk_id:
                return

        # Insert new values
        if is_new:
            self.__insert(ou_id, aff_code, disk_id)
        else:
            self.__update(ou_id, aff_code, disk_id)

    def search(self, ou_id, aff_code=NotSet, any_status=True):
        """
        Search for rows matching ou, aff, status

        Similar to get but allows NotSet for aff_code and status_code so that
        one can find all entries for an OU or OU+aff combination

        :param int ou_id: entity_id of the ou

        :type aff_code: int, None
        :param aff_code: Cerebrum person aff (status) constant

        :param bool any_status: Look for any matching status if aff_code is set
         to a person affiliation

        :rtype: db.row
        :return: ou_id, aff_code, status_code, disk_id
        """
        binds = {
            'ou_id': int(ou_id),
        }

        where = "ou_id = :ou_id"
        if aff_code is None:
            where += " AND aff_code IS NULL AND status_code IS NULL"
        elif aff_code is NotSet:
            pass
        else:
            aff_code, status_code = aff_lookup(self.const, int(aff_code))
            where += " AND aff_code = :aff_code"
            binds['aff_code'] = int(aff_code)
            if status_code is None:
                if not any_status:
                    where += " AND status_code IS NULL"
            else:
                where += " AND status_code = :status_code"
                binds['status_code'] = int(status_code)

        stmt = """
          SELECT ou_id, aff_code, status_code, disk_id
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE {where}
        """.format(where=where)
        return self.query(stmt, binds)
