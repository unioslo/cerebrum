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

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Disk import Disk
from .constants import CLConstants


class OuDiskMapping(DatabaseAccessor):
    def __init__(self, database):
        super(OuDiskMapping, self).__init__(database)
        self.disk = Disk(self._db)

    def __insert(self, ou_id, aff_code, status_code, disk_id):
        """
        Insert a new row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int disk_id: entity_id of the disk
        """
        binds = {
            'ou_id': ou_id,
            'aff_code': aff_code,
            'status_code': status_code,
            'disk_id': disk_id,
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=ou_disk_mapping]
            (ou_id, aff_code, status_code, disk_id)
          VALUES
            (:ou_id, :aff_code, :status_code, :disk_id)
        """
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(disk_id)
        self._db.log_change(int(ou_id), CLConstants.ou_disk_add, None,
                            change_params={
                                'aff': str(aff_code),
                                'status': status_code,
                                'path': six.text_type(self.disk.path),
                            })

    def __update(self, ou_id, aff_code, status_code, disk_id):
        """
        Update a row in the ou_disk_mapping table.

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int disk_id: entity_id of the disk
        """
        binds = {
            'ou_id': ou_id,
            'aff_code': aff_code,
            'status_code': status_code,
            'disk_id': disk_id,
        }

        stmt = """
          UPDATE [:table schema=cerebrum name=ou_disk_mapping]
          SET 
            disk_id = :disk_id
          WHERE
            ou_id = :ou_id
            AND
            (aff_code = :aff_code OR (aff_code is NULL AND
                                      :aff_code IS NULL))
            AND
            (status_code = :status_code OR (status_code is NULL AND
                                            :status_code IS NULL))
        """
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(disk_id)
        self._db.log_change(int(ou_id), CLConstants.ou_disk_add, None,
                            change_params={
                                'aff': str(aff_code),
                                'status': status_code,
                                'path': six.text_type(self.disk.path),
                            })

    def delete(self, ou_id, aff_code, status_code):
        """
        Delete disk_id for a given ou_id and aff_code

        :param int ou_id: entity_id of the ou
        :param int or None aff_code: int of affiliation constant
        :param int or None status_code: int or aff status constant
        """
        data = self.get(ou_id, aff_code, status_code)
        disk_id = data.get('disk_id')

        binds = {'ou_id': ou_id,
                 'aff_code': aff_code,
                 'status_code': status_code,
                 }
        stmt = """
          DELETE FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE
            ou_id = :ou_id
            AND
            (aff_code = :aff_code OR (aff_code is NULL AND
                                      :aff_code IS NULL))
            AND
            (status_code = :status_code OR (status_code is NULL AND
                                            :status_code IS NULL))
        """
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(disk_id)
        self._db.log_change(int(ou_id), CLConstants.ou_disk_remove, None,
                            change_params={
                                'aff': aff_code,
                                'status': status_code,
                                'path': six.text_type(self.disk.path)}
                            )

    def get_disk(self, disk_id):
        # TODO: Give this a better name! We are not getting a disk
        """
        Get all OUs and Affiliations that use a disk_id

        :param int disk_id:
        :return: list of db.rows with keys ou_id, aff_code, disk_id
        """
        binds = {'disk_id': disk_id,
                 }
        stmt = """
          SELECT ou_id, aff_code, status_code
          FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE
            disk_id = :disk_id
        """
        return self.query(stmt, binds)

    def get(self, ou_id, aff_code, status_code):
        """
        Get values for a given combination of ou (and affiliation).

        :param int ou_id: entity_id of the ou

        :type aff_code: int, None or 'null'
        :param aff_code: int or 'null' for specific entry, None for any

        :type status_code: int, None or 'null'
        :param status_code: int or 'null' for specific entry, None for any

        :return: list of db.rows with keys ou_id, aff_code, disk_id
        """
        binds = {
            'ou_id': ou_id,
        }
        where = "ou_id = :ou_id"
        if aff_code:
            if aff_code == 'null':
                where += " AND aff_code is NULL"
            else:
                where += " AND aff_code = :aff_code"
                binds['aff_code'] = int(aff_code)
        if status_code:
            if status_code == 'null':
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

    def set(self, ou_id, aff_code, status_code, disk_id):
        """
        Set disk_id for a given combination of ou and affiliation

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int or None status_code: int of affiliation status constant
        :param int disk_id: entity_id of the disk
        """
        # Check old values
        old_aff = 'null' if aff_code is None else aff_code
        old_status = 'null' if status_code is None else status_code
        old_values = self.get(ou_id, old_aff, old_status)

        # Check if anything is new
        if old_values and old_values[0].get('disk_id') == disk_id:
            return

        # Insert new values
        aff_code = None if aff_code == 'null' else aff_code
        status_code = None if status_code == 'null' else status_code
        if not old_values:
            self.__insert(ou_id, aff_code, status_code, disk_id)
        else:
            self.__update(ou_id, aff_code, status_code, disk_id)

    def clear(self, ou_id, aff_code, status_code):
        """
        Delete disk_id for a given combination of ou and affiliation

        :param int ou_id: entity_id of the ou
        :param int aff_code: int of affiliation constant
        :param int status_code: int of aff status constant
        """
        old_aff = 'null' if aff_code is None else aff_code
        old_status = 'null' if status_code is None else status_code
        old_values = self.get(ou_id, old_aff, old_status)

        if not old_values:
            # Nothing to update
            return
        disk_id = old_values[0].get('disk_id')
        binds = {'ou_id': ou_id,
                 }
        where = "ou_id = :ou_id"
        if aff_code:
            if aff_code == 'null':
                where += " AND aff_code is NULL"
            else:
                where += " AND aff_code = :aff_code"
                binds['aff_code'] = int(aff_code)
        if status_code:
            if status_code == 'null':
                where += " AND status_code IS NULL"
            else:
                where += " AND status_code = :status_code"
                binds['status_code'] = int(status_code)
        stmt = """
          DELETE FROM [:table schema=cerebrum name=ou_disk_mapping]
          WHERE {}
        """.format(where)
        self.execute(stmt, binds)

        self.disk.clear()
        self.disk.find(disk_id)
        self._db.log_change(ou_id, CLConstants.ou_disk_remove, None,
                            change_params={'aff': aff_code,
                                           'status': status_code,
                                           'path': self.disk.path})
