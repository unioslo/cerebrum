#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

"""This Module ads expire_date to any Entity. It will enable basic
functionality to administer the new attribute. For example
L{EntityExpire._set_expire_date}, L{EntityExpire._delete_expire_date},
L{EntityExpire.is_expired}, etc.

The Entity module itself must guarantee that its API functions
follow the expire_date. All list functions, find, etc. should
implement an extra optional argument named C{expired_before}, a
string formatted 'YYYYMMDD' or a date/time variable.
This argument should be treated such that:
  - C{expire_date < :expired_before} is considered EXPIRED
  - C{expire_date >= :expired_before} is considered NON-EXPIRED
  - if C{expired_before} is not given, thus C{expired_before} is
    C{None}, C{:expired_before} should be considered C{[:now]}

A LEFT JOIN is among the methods that can be used to check if an
entity has expired. An example Pseudo-SQL that will produce a list over
all NON-EXPIRED OUs follows::

  SELECT *
  FROM [:table schema=cerebrum name=ou_info] oi
  LEFT JOIN [:table schema=cerebrum name=entity_expire] ee
  ON ee.entity_id = oi.ou_id
  WHERE (ee.expire_date<[:now] OR ee.expire_date IS NULL)

The C{OR ee.expire_date IS NULL} is essential for considering
entitites with no entries in the C{entity_expire} table NON-EXPIRED.

The only two attributes of the C{entity_expire} table are C{expire_date}
and C{entity_id}.

These guidelines will guarantee a consistent handlig of expire
dates and should be followed religiously.

"""


import sys
from exceptions import Exception

import cerebrum_path
import cereconf

from Cerebrum.Constants import Constants
from Cerebrum.Utils import NotSet
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum.Entity import Entity
from Cerebrum import Errors


class EntityExpireConstants(Constants):
    """Constants specific for C{EntityExpire}."""
    entity_expire_add = _ChangeTypeCode(
        "entity_expire", "add",
        "added expire date for %(subject)s",
        ("new_expire_date=%(new_expire_date)s",))
    entity_expire_del = _ChangeTypeCode(
        "entity_expire", "del",
        "deleted expire date for %(subject)s",
        ("old_expire_date=%(old_expire_date)s",))
    entity_expire_mod = _ChangeTypeCode(
        "entity_expire", "mod",
        "modified expire date for %(subject)s",
        ("old_expire_date=%(old_expire_date)s",
         "new_expire_date=%(new_expire_date)s"))


class EntityExpiredError(Exception):
    """Exception class - Thrown when an entity has expired."""
    pass


class EntityExpire(Entity):
    """
    Mixin class that will enable basic expire date functionality
    to any given entity.

    """
    __read_attr__ = ()
    __write_attr__ = ('_expire_date',)

    def clear(self):
        """Clears current object instance."""
        self._expire_date = NotSet
        self.__updated = []
        self.__super.clear()

    def delete(self):
        """Deletes current object from DB."""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_expire]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def populate_expire_date(self, expire_date):
        """Sets expire date on current object instance.

        @param expire_date: If expire_date is None, deletion is assumed.
        @type expire_date: String on format YYYYMMDD or Date/Time.
        @return: Void.

        """
        self._expire_date = expire_date

    def write_db(self):
        """Writes changes in current object to database."""
        self.__super.write_db()
        if self._expire_date is not NotSet:
            if '_expire_date' in self.__updated:
                if self._expire_date is None:
                    self._delete_expire_date()
                else:
                    self._set_expire_date(self._expire_date)

    def _set_expire_date(self, expire_date=None):
        """
        Will set C{expire_date} on an entity. C{expire_date} should not
        be set for entitites that do not have a defined date on
        which they seize to exist.

        @param expire_date: If expire_date is None, [:now] is assumed.
        @type expire_date: String on format YYYYMMDD or Date/Time.
        @return: Void.

        """

        expiry_set = None
        try:
            expiry_set = self.query_1(
                """SELECT expire_date
                FROM [:table schema=cerebrum name=entity_expire]
                WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            expiry_set = None

        if expiry_set is not None:
            self.execute("""
                UPDATE [:table schema=cerebrum name=entity_expire]
                SET expire_date=:exp_date
                WHERE entity_id=:e_id""",
                         {'exp_date': expire_date,
                          'e_id': self.entity_id})
            parameters = {}
            parameters['old_expire_date'] = str(expiry_set)
            parameters['new_expire_date'] = str(expire_date)
            self._db.log_change(self.entity_id,
                                self.const.entity_expire_mod,
                                None,
                                change_params=parameters)
        else:
            self.execute("""
                INSERT INTO
                    [:table schema=cerebrum name=entity_expire]
                (entity_id, expire_date) VALUES (:e_id, :exp_date)""",
                         {'e_id': self.entity_id,
                          'exp_date': expire_date})
            parameters = {}
            parameters['new_expire_date'] = str(expire_date)
            self._db.log_change(self.entity_id,
                                self.const.entity_expire_add,
                                None,
                                change_params=parameters)

    def _delete_expire_date(self):
        """
        Removes expire_date for current entity.

        """

        expiry_set = None
        try:
            expiry_set = self.query_1(
                """SELECT expire_date
                FROM [:table schema=cerebrum name=entity_expire]
                WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            expiry_set = None

        self.execute("""
            DELETE FROM [:table schema=cerebrum name=entity_expire]
            WHERE entity_id=:e_id""",
                     {'e_id': self.entity_id})
        parameters = {}
        parameters['old_expire_date'] = str(expiry_set)
        self._db.log_change(self.entity_id,
                            self.const.entity_expire_del,
                            None,
                            change_params=parameters)

    def find(self, entity_id, expired_before=None):
        """Find with filter on expire date.

        @param expired_before: See L{EntityExpire.is_expired}.

        """

        # Find object
        self.__super.find(entity_id)

        # If the find doesn't fail, we can assume the OU is found and
        # already in memory. Now check if it's not expired!
        if self.is_expired(expired_before=expired_before):
            tmp_id = self.entity_id
            self.__super.clear()
            raise EntityExpiredError('Entity %s expired.' % tmp_id)

        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def is_expired(self, entity_id=None, expired_before=None):
        """
        Will check if an entity has expired or not.

        @param entity_id: Will be used instead of C{self.entity_id} if
                  C{entity_id is not None}. This function may therefore
                  be used to check the expired status of any entity, not
                  only the current one.
        @type entity_id: Integer.
        @param expired_before: Date for which the query should be done.
                  If C{expire_date} of an entity is C{20070101} and
                  C{expired_before > 20070101}, the entity  will be
                  considered expired. Otherwise, the entity will be
                  considered non-expired. If expired_before is None,
                  B{current time} will be used. Note, this also includes
                  hours and minutes, so immediately after midnight,
                  any entity with C{expire_date} set to that day will be
                  considered expired.
        @type expired_before: String (YYYYMMDD), or DateTime var.
        @return: Bolean.
            - True if expired.
            - False otherwise.

        """

        if entity_id is None:
            entity_id = self.entity_id

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=entity_expire] ee")
        where.append("ee.entity_id=:entity_id")

        if expired_before is None:
            where.append("(ee.expire_date < [:now])")
        else:
            where.append("(ee.expire_date < :date)")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        try:
            self.query_1("""
                    SELECT ee.entity_id
                    FROM %s %s""" %
                         (','.join(tables), where_str),
                         {'entity_id': entity_id,
                          'date': expired_before})
            return True
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            return False

    def get_expire_date(self, entity_id=None):
        """
        Obtains the expire_date of the given entity.

        @param entity_id: Will be used instead of C{self.entity_id} if
                  C{entity_id is not None}. This function may
                  therefore be used to get the expire date of any
                  entity, not only the current one.
        @type entity_id: Integer.
        @return: DateTime.
            - Current 'expire_date'.
            - None if no date is set.

        """

        if entity_id is None:
            entity_id = self.entity_id

        try:
            res = self.query_1(
                """SELECT expire_date
                FROM [:table schema=cerebrum name=entity_expire]
                WHERE entity_id=:e_id""",
                {'e_id': entity_id})
            return res  # ('expire_date')
        except Errors.TooManyRowsError:
            raise Errors.TooManyRowsError
        except Errors.NotFoundError:
            return None

    def list_expired(self, entity_type=None, expired_before=None):
        """
        Obtains a list over expired entities.

        @param entity_type: The type of entities one wishes to be
                  returned from the function. If C{entity_type is None},
                  entities of all kinds will be listed.
        @type entity_type: Integer (C{entity_type_code}).
        @param expired_before: See L{is_expired}
        @type expired_before:
        @return: List of Tuples C{[(entity_id, DateTime),]}
            A list with C{entity_id}s and their C{expire_date}s. Note
            That the list only will include entities with expire
            dates before C{[:now]} or C{expired_before}.

        """

        tables = []
        where = []
        tables.append("[:table schema=cerebrum name=entity_expire] ee")

        if entity_type is not None:
            tables.append("[:table schema=cerebrum \
                             name=entity_info] ei")
            where.append("ee.entity_id=ei.entity_id")
            where.append("ei.entity_type=:entity_type")

        if expired_before is None:
            where.append("(ee.expire_date < [:now])")
        else:
            where.append("(ee.expire_date < :date)")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
                            SELECT ee.entity_id, ee.expire_date
                            FROM %s %s""" %
                          (','.join(tables), where_str),
                          {'entity_type': entity_type,
                           'date': expired_before})
