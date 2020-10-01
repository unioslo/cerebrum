# -*- coding: utf-8 -*-
#
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
"""
Abstract mapper for HR imports.

The mapper is responsible for translating the raw data from a datasource into
HR objects, as well as mapping external objects to local objects (e.g.  find a
Cerebrum.Person object from employee data).
"""
import datetime
import abc

import six

from Cerebrum.Utils import Factory
from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
)
from Cerebrum.config.settings import Integer


class MapperError(RuntimeError):
    """ Unable to fetch data. """
    pass


class NoMappedObjects(MapperError):
    """ Unable to map object - no matches. """
    pass


class ManyMappedObjects(MapperError):
    """ Unable to map object - multiple matches. """
    pass


def in_date_range(value, start=None, end=None):
    """ Check if a date is in a given range. """
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


@six.add_metaclass(abc.ABCMeta)
class AbstractMapper(object):
    """
    Fetch objects from remote systems.
    """

    def __init__(self, db, config):
        """
        :param db: Database object
        :type db: Cerebrum.Database
        """
        self.db = db
        self.end_grace = datetime.timedelta(days=config.end_grace)
        self.start_grace = datetime.timedelta(days=config.start_grace)
        self.const = Factory.get('Constants')(db)

    @abc.abstractproperty
    def source_system(self):
        """ The source system to map this data to. """
        pass

    @abc.abstractmethod
    def translate(self, reference, obj):
        """
        Translate datasource into a remote object.

        :type reference: six.text_type
        :param reference:
            An object reference, as provided by
            :meth:`AbstractDatasource.get_reference`

        :type obj: object
        :param obj:
            An object, as provided by :meth:`AbstractDatasource.get_object`

        :rtype: models.HRPerson
        """
        pass

    @abc.abstractmethod
    def find_entity(self, hr_object):
        """
        Find a Cerebrum object/entity.

        :type hr_object: models.HRPerson
        :param obj: An object, as provided by :meth:`.translate`.

        :rtype: Cerebrum.Person.Person

        :raises NoMappedObjects: No entity can be found
        :raises ManyMappedObjects: Multiple entities can be found
        """
        pass

    @abc.abstractmethod
    def is_active(self, hr_object):
        """
        Decide if an HR object should be present in the database.

        :type hr_object: models.HRPerson

        :rtype: bool
        """
        pass

    def needs_delay(self, hr_object):
        """
        Examine object and decide additional future date triggers.

        Some changes are *future* updates that needs additional processing at a
        given date.  This method examines an object and returns a list of
        date or datetime objects for this purpose.

        These dates should be stored in a queue along with the original
        message or object reference, and re-processed at a later time.

        :type hr_object: Cerebrum.modules.hr_import.models.HRPerson

        :returns:
            - A list of date or datetime objects for future processing.
            - A bool stating whether the person has at least one active
              affiliation.
        """
        t = datetime.date.today()
        start_cutoff = t + self.start_grace
        end_cutoff = t + self.end_grace

        active_date_ranges = []

        for a in hr_object.affiliations:
            active_date_ranges.append((a.start_date, a.end_date))

        retry_dates = []
        has_active_affiliation = False

        for start, end in active_date_ranges:
            if (not in_date_range(start_cutoff, start=start)
                    and in_date_range(end_cutoff, end=end)):
                retry_dates.append(start_cutoff)
            else:
                has_active_affiliation = True

        return retry_dates, has_active_affiliation


class MapperConfig(Configuration):
    start_grace = ConfigDescriptor(
        Integer,
        default=0,
        doc=("How many days after an affiliation's start date should it first "
             "be imported?"),
    )

    end_grace = ConfigDescriptor(
        Integer,
        default=0,
        doc=("How many days past an affiliation's end date should it be kept "
             "in Cerebrum?"),
    )
