# -*- coding: utf-8 -*-
# Copyright 2011-2015 University of Oslo, Norway
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

import datetime
import mx.DateTime
import six

import cerebrum_path

from Cerebrum.Utils import argument_to_sql


__version__ = '1.0'  # Should match design/mod_employment.sql
del cerebrum_path


class PersonEmploymentMixin(object):
    """Mixin for dealing with employment data registration.

    See mod_employment.sql and friends.

    This class is meant to be used together with other Person components
    (i.e. it won't be very useful on its own).
    """

    __table = "[:table schema=cerebrum name=person_employment]"

    def write_db(self):
        super(PersonEmploymentMixin, self).write_db()

    def delete(self):
        self.execute("""
        DELETE FROM %s
        WHERE person_id = :person_id
        """ % self.__table, {"person_id": self.entity_id})
        super(PersonEmploymentMixin, self).delete()

    def _human2mxDateTime(self, something):
        """Make an mx.DateTime out of something.

        Let's try to be nice to callers and accept the following syntaxes and
        types:

          * 2011-12-31
          * 20111231
          * <mx.DateTime instance>
          * <datetime.datetime> instance
        """

        if isinstance(something, mx.DateTime.DateTimeType):
            return something

        if isinstance(something, (str, unicode)):
            block = something.replace("-", "")
            return mx.DateTime.strptime(block, "%Y%m%d")

        if isinstance(something, (datetime.datetime,
                                  datetime.date)):
            return mx.DateTime.DateTime(something.year,
                                        something.month,
                                        something.day)
        assert False, "Unknown format for date %s" % repr(something)

    def add_employment(self, ou_id, description, source_system,
                       percentage, start_date, end_date,
                       employment_code=None, main_employment=True):
        """Add (or update) a specific employment entry for a person.
        """

        assert main_employment in (True, False)

        binds = {"person_id": self.entity_id,
                 "ou_id": int(ou_id),
                 "description": description,
                 "source_system": int(
                     self.const.AuthoritativeSystem(source_system)),
                 "employment_code": str(employment_code),
                 "percentage": float(percentage),
                 "start_date": self._human2mxDateTime(start_date),
                 "end_date": self._human2mxDateTime(end_date),
                 "main_employment": main_employment and "T" or "F"}

        existing = list(self.search_employment(self.entity_id,
                                               ou_id, description,
                                               source_system))
        if not existing:
            self.execute("""
            INSERT INTO %s VALUES
            (:person_id, :ou_id, :description, :source_system,
             :employment_code, :main_employment, :percentage,
             :start_date, :end_date)
             """ % self.__table, binds)
            return

        # An entry exists. There has to be exactly 1 (since the fields specified
        # constitute a primary key).
        row = existing[0]
        # If there is a difference, run an update... (otherwise do nothing)
        if (binds["employment_code"] != row["employment_code"] or
                binds["start_date"] != row["start_date"] or
                binds["end_date"] != row["end_date"] or
                abs(binds["percentage"] - row["percentage"]) > 0.1 or
                main_employment != row["main_employment"]):

            self.execute("""
            UPDATE %s SET
                employment_code = :employment_code,
                start_date = :start_date,
                end_date = :end_date,
                percentage = :percentage,
                main_employment = :main_employment
            WHERE
                person_id = :person_id AND
                ou_id = :ou_id AND
                description = :description AND
                source_system = :source_system
            """ % self.__table, binds)

    def delete_employment(self, ou_id, description, source_system):
        """Remove a specific entry from person_employment.

        If it does not exist, the method is essentially a no-op.
        """

        binds = {"person_id": self.entity_id,
                 "ou_id": int(ou_id),
                 "description": description,
                 "source_system": self.const.AuthoritativeSystem(source_system),
                 }
        self.execute("""
        DELETE FROM %s
        WHERE person_id = :person_id AND
              ou_id = :ou_id AND
              description = :description AND
              source_system = :source_system
        """ % self.__table, binds)

    def search_employment(self, person_id=None, ou_id=None, description=None,
                          source_system=None, employment_code=None,
                          include_expired=True, main_employment=None):
        """Look for employment entries matching certain criteria.

        @type person_id: int or a sequence thereof or None.
        @param person_id:
          Filter the results by person_id.

        @type ou_id: int or a sequence thereof or None.
        @param ou_id:
          Filter the results by ou_id.

        @type employment: int or constant or a sequence thereof or None.
        @param person_id:
          Filter the results by the specific employment(s).

        @type include_expired: bool
        @param include_expired:
          Filter out results that has an end date in the past.

        @type main_employment: bool
        @param main_employment:
          Only return results defined as the person's main employment.

        @rtype: iterable over db_rows
        @return:
          Whichever rows match the filters specified. Without any filters,
          return the entire table.
        """

        where = list()
        binds = {}
        if person_id is not None:
            where.append(argument_to_sql(person_id, "person_id", binds, int))
        if ou_id is not None:
            where.append(argument_to_sql(ou_id, "ou_id", binds, int))
        if description is not None:
            where.append(argument_to_sql(description, "description",
                                         binds, six.text_type))
        if source_system is not None:
            where.append(argument_to_sql(source_system, "source_system",
                                         binds, int))
        if employment_code is not None:
            where.append(argument_to_sql(employment_code, "employment_code",
                                         binds, str))
        if main_employment:
            where.append(argument_to_sql('T', "main_employment", binds, str))
        if not include_expired:
            where.append('(end_date IS NULL OR end_date > [:now])')

        query = """
        SELECT person_id, ou_id, description, source_system,
               employment_code, main_employment, percentage, start_date,
               end_date
        FROM %s
        WHERE %s
        """ % (self.__table, " AND ".join(where))

        # This voodoo is necessary to hide how we represent booleans in the db.
        for row in self.query(query, binds, fetchall=False):
            if row["main_employment"] == 'T':
                row["main_employment"] = True
            elif row["main_employment"] == 'F':
                row["main_employment"] = False
            else:
                assert False, "This cannot happen!"
            yield row
