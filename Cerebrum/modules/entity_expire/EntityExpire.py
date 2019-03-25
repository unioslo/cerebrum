# -*- coding: utf-8 -*-

# Copyright 2003, 2004, 2019 University of Oslo, Norway
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

from Cerebrum.Utils import NotSet
from Cerebrum.Entity import Entity
from Cerebrum.modules.entity_expire import entity_expire_db


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

    def delete_expire_date(self):
        """Deletes current object from DB."""
        entity_expire_db.delete_expire_date(self._db, self.entity_id)
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
                    entity_expire_db.delete_expire_date(self._db,
                                                        self.entity_id)
                else:
                    entity_expire_db.set_expire_date(self._db,
                                                     self.entity_id,
                                                     self._expire_date)

    def find(self, entity_id, expired_before=None):
        """ Find with filter on expire date.

        :param entity_id: Cerebrum.Entity entity_id
        :type entity_id: int

        :param expired_before: See L{entity_expire_db.is_expired}.

        """

        # Find object
        self.__super.find(entity_id)

        # If the find doesn't fail, we can assume the OU is found and
        # already in memory. Now check if it's not expired!
        if entity_expire_db.is_expired(self.db, self.entity_id,
                                       expired_before=expired_before):
            tmp_id = self.entity_id
            self.__super.clear()
            raise EntityExpiredError('Entity %s expired.' % tmp_id)

        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []
