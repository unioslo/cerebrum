# -*- coding: utf-8 -*-
#
# Copyright 2020-2022 University of Oslo, Norway
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

The mapper is responsible for translating data from a datasource into
actual types and values for Cerebrum.

The py:method:`.AbstractMapper.translate` function turns a complete set of
hr-data into a py:class:`.HrPerson`.  The latter is a collection of all the
external ids, affiliations, etc... that could be of relevance in the import.
"""
import datetime
import abc
import logging

import six

from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import Integer, Iterable, String
from Cerebrum.utils.reprutils import ReprFieldMixin

logger = logging.getLogger(__name__)


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

    def __init__(self, config):
        """
        # TODO: beskrivelse for config-argumentet?
        """
        # TODO: We should probably rename the settings to make the "polarity"
        # of the value clearer, and then *not* abs() the values here.  This
        # should be fine, though, as there aren't really any good reason to
        # turn these any other way around.
        #
        # Also, should this really be config? Maybe, maybe not.
        self.start_offset = -1 * datetime.timedelta(abs(config.start_grace))
        self.end_offset = datetime.timedelta(days=abs(config.end_grace))

        # TODO: Do we really need to *ignore* these dates?  The only reason to
        # ignore values, would be to ignore any end-dates/future task that is
        # unreasonably far into the future.  Probably better to just have a
        # sliding cutoff, e.g. ignore anything more than 10, 50, 100 years
        # ahead in time.
        self.end_dates_ignore = [
            datetime.datetime.strptime(x, '%Y-%m-%d').date()
            for x in config.end_dates_ignore]

        # TODO: is this really config?  If so, why this and not the mg/mug
        # roles?  These settings are never really used in the new import, but
        # hardcoded into the appropriate mapper subclass.
        #
        # Also this is the abstract import -- dfo_category_id isn't really
        # something this mapper should know about...
        self.status_mapping = {
            x['dfo_category_id']: x['cerebrum_status']
            for x in config.status_mapping}

    @abc.abstractmethod
    def translate(self, reference, source):
        """
        Translate datasource into an importable object.

        :type reference: six.text_type
        :param reference:
            An object reference, as provided by
            :meth:`AbstractDatasource.get_reference`

        :type data: dict
        :param data:
            A data object, as provided by :meth:`AbstractDatasource.get_object`

        :rtype: object
        """
        pass

    @abc.abstractmethod
    def is_active(self, hr_object):
        """
        Decide if an HR object should be present in the database.

        :param object hr_object: result from py:meth:`.translate`

        :rtype: bool
        """
        pass

    def needs_delay(self, hr_object, _today=None):
        """ Find relevant start or end dates that requires future updates.

        :param object hr_object: result from py:meth:`.translate`

        :rtype: list
        :returns: a list of date objects
        """
        today = _today or datetime.date.today()
        start_cutoff = today + self.start_offset
        end_cutoff = today + self.end_offset
        active_date_ranges = []

        for aff, ou, start_date, end_date in hr_object.affiliations:
            active_date_ranges.append((start_date, end_date))

        # TODO: Add roles?
        retry_dates = set()
        for start, end in active_date_ranges:
            if not in_date_range(start_cutoff, start=start):
                # Start of affiliation is in the future
                retry_date = start + self.start_offset
                retry_dates.add(retry_date)
                logger.info('affiliation start %s, should retry at %s',
                            start, retry_date)
                # No need to handle the the end date now.
                continue
            if (end not in self.end_dates_ignore and
                    in_date_range(end_cutoff, end=end)):
                # We have to try again the day after the affiliations end date
                # if we are actually going to remove it. Thus the + 1
                retry_date = end + self.end_offset + datetime.timedelta(days=1)
                retry_dates.add(retry_date)
                logger.info('affiliation end %s, should retry at %s',
                            end, retry_date)

        if hr_object.start_date and not hr_object.affiliations:
            if (hr_object.start_date > today):
                retry_dates.add(hr_object.start_date)
                logger.info("no affiliations to consider, "
                            "should retry at %s (employee start date)",
                            hr_object.start_date)

        return retry_dates


class HrPerson(ReprFieldMixin):

    repr_module = False
    repr_id = False
    repr_fields = ('hr_id', 'enable')

    def __init__(self, hr_id, birth_date, gender, enable):
        self.hr_id = hr_id
        self.birth_date = birth_date
        self.gender = gender
        self.enable = enable

        self.start_date = None
        self.affiliations = []
        self.contacts = []
        self.ids = []
        self.names = []
        self.titles = []


class StatusMapping(Configuration):

    # TODO: Obsolete?

    dfo_category_id = ConfigDescriptor(
        Integer,
        doc='Position category id'
    )
    cerebrum_status = ConfigDescriptor(
        String,
        doc='Corresponding cerebrum status'
    )


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

    end_dates_ignore = ConfigDescriptor(
        Iterable,
        template=String(),
        default=[],
        doc='End dates representing contracts without an end date..'
            'E.g. 9999-12-31 is used by UiO-SAP.'
    )

    status_mapping = ConfigDescriptor(
        Iterable,
        template=Namespace(config=StatusMapping),
        default=[],
        doc='Mapping between category in SAP and status in Cerebrum.'
    )
