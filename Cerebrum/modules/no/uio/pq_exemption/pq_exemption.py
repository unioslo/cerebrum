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
"""Contains routines for updating the printer_quotas table

The table contains entries for all persons that *should not* have a printer
quota at UiO. There will *not* be an entry for the person if they *should*
have a printer quota.

The point of all of this is to keep track of which persons at the University of
Oslo have printer quotas. This is exported to the LDAP by calling the
PrinterQuotas.list method defined below. For this to return anything, the
database has to be populated, which is done with the script located at
contrib/no/uio/pq_exemption/quota_update.py
"""
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Errors import NotFoundError
from Cerebrum.Person import Person
from Cerebrum.Utils import Factory


class PrinterQuotaExemption(DatabaseAccessor):
    """Database accessor class for the printer_quotas table"""

    def __init__(self, database):
        super(PrinterQuotaExemption, self).__init__(database)
        self.clconst = Factory.get('CLConstants')(database)
        self.default_exemption = True

    def list(self, only_without_exempt=True):
        """List exempt info for all persons in the db table

        :param bool only_without_exempt: True or False
        :return: Only those without exempt if only_without_exempt=True, else
                 everyone in the db table
        :rtype: db_row
        """
        where = ''
        if only_without_exempt:
            where = """WHERE exempt = FALSE"""
        return self.query(
            """
            SELECT person_id, exempt
            FROM [:table schema=cerebrum name=printer_quotas]
            """ + where
        )

    def set(self, person_id, exempt=True):
        """Register person in the pq_exemption table

        :param int person_id: entity id of a person
        :param bool exempt: True if the person is exempt, otherwise False
        :return: None
        """
        try:
            old_values = self.get(person_id)
            is_new = False
        except NotFoundError:
            old_values = {}
            is_new = True

        if not is_new and old_values['exempt'] == exempt:
            # Prevent false changes
            return

        if is_new:
            self.__insert(person_id, exempt)
        else:
            self.__update(person_id, exempt)

    def __insert(self, person_id, exempt):
        """Insert new row

        :param person_id:
        :param exempt:
        :return:
        """
        binds = {'person_id': person_id,
                 'exempt': exempt,
                 }
        self.execute(
            """
            INSERT INTO [:table schema=cerebrum name=pq_exemption]
            (person_id, exempt) VALUES (:person_id, :exempt)
            """,
            binds)
        self._db.log_change(person_id,
                            self.clconst.printer_quota_exempt_add,
                            None,
                            change_params={'exempt': exempt})

    def __update(self, person_id, exempt):
        """Update old row

        :param int person_id: entity_id
        :param bool exempt:
        :return:
        """
        binds = {'person_id': person_id,
                 'exempt': exempt,
                 }
        self.execute(
            """
            UPDATE [:table schema=cerebrum name=pq_exemption]
            SET exempt=:exempt
            WHERE person_id=:person_id
            """,
            binds)
        self._db.log_change(person_id,
                            self.clconst.printer_quota_exempt_upd,
                            None,
                            change_params={'exempt': exempt})

    def __delete(self, person_id):
        """Delete row

        :param int person_id: entity_id
        :return:
        """
        binds = {'person_id': person_id,
                 }
        self.execute(
            """
            DELETE FROM [:table schema=cerebrum name=pq_exemption]
            WHERE person_id=:person_id
            """,
            binds)
        self._db.log_change(person_id,
                            self.clconst.printer_quota_exempt_rem,
                            None)

    def get(self, person_id):
        """
        Get the exempt info of a single person if there is an entry for the
        person

        :param int person_id: entity id of a person
        :return:
        :rtype: db_row
        """
        binds = {'person_id': person_id,
                 }
        return self.query_1(
            """
            SELECT person_id, exempt
            FROM [:table schema=cerebrum name=pq_exemption]
            WHERE person_id=:person_id
            """,
            binds
        )

    def exists(self, person_id):
        """Check if person exists in db table

        :param person_id:
        :return:
        """
        binds = {'person_id': person_id}
        return self._db.query_1(
            """
            SELECT EXISTS(
              SELECT 1 FROM [:table schema=cerebrum name=pq_exemption]
              WHERE person_id=:person_id)
            """, binds
        )

    def clear(self, person_id):
        """Remove quota info for a single person

        :param int person_id: entity id of a person
        :return: None
        """
        if self.exists(person_id):
            self.__delete(person_id)

    def is_exempt(self, person_id):
        """Check if a person is exempt from the printer quota regime

        :param int person_id: entity_id of a person
        :return bool: Whatever is stored in the table.
        If nothing is stored we return True
        """
        try:
            quota = self.get(person_id)
        except NotFoundError:
            return self.default_exemption
        else:
            return quota['exempt']


class PersonPrinterMixin(Person):
    """Take care of printer related things for Person objects"""
    def delete(self):
        """Delete the quota entry for this entity"""
        PrinterQuotaExemption(self._db).clear(person_id=self.entity_id)
        super(PersonPrinterMixin, self).delete()
