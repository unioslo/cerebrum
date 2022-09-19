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
Abstract HR import routine.

The importers binds together the datasources and mappers, and are responsible
for performing the actual database updates.
"""
import abc
import datetime
import logging
import json

from Cerebrum.modules.import_utils.matcher import PersonMatcher
from Cerebrum.utils.date import now
from Cerebrum.utils import date_compat

from .datasource import DatasourceInvalid

logger = logging.getLogger(__name__)


def load_message(event):
    """ Extract message body from event.

    :type event: Cerebrum.modules.amqp.handlers.Event
    :param event:
        A notification that contains a reference to the modified object.
    :rtype: dict
    """
    try:
        body = json.loads(event.body)
        logger.debug('load_message: parsed content, event=%r', event)
    except Exception as e:
        logger.debug('load_message: unable to parse content, event=%r', event)
        raise DatasourceInvalid('Invalid event format: %s (%r)' %
                                (e, event.body))
    return body


class AbstractImport(object):

    # ID types that leads to a definite match in Cerebrum.  This will typically
    # contain the primary id type for the source system that we're using
    # (e.g.  DFO_PID for DFO_SAP)
    MATCH_ID_TYPES = ()

    def __init__(self, db, datasource, mapper, source_system):
        self.db = db
        self._datasource = datasource
        self._mapper = mapper
        self._source_system = source_system

    @property
    def datasource(self):
        """ A datasource to use for fetching HR data. """
        return self._datasource

    @property
    def mapper(self):
        """ A mapper to use for translating HR data to Cerebrum. """
        return self._mapper

    @property
    def source_system(self):
        """ A source system to link import data to. """
        return self._source_system

    def find_entity(self, hr_object):
        """ Find matching Cerebrum object for the given hr_object. """
        search = PersonMatcher(self.MATCH_ID_TYPES)
        criterias = tuple(hr_object.ids)
        if not criterias:
            raise ValueError('invalid person: no external_ids')
        return search(self.db, criterias, required=False)

    def handle_reference(self, reference):
        """
        Initiate import from a reference.

        This is the entrypoint for use with e.g. scripts, or when processing
        tasks.  Fetches the referred object from the datasource and calls
        `handle_object(datasource-object)`.
        """
        raw_data = self.datasource.get_object(reference)
        return self.handle_object(raw_data)

    def handle_object(self, raw_data):
        """
        Initiate import using an object from a datasource.

        This is usually triggered by `handle_reference`, but can be called
        directly to e.g. run a test import from fixtures.

        It will use the mapper to extract relevant data from the raw_data given
        as input, find a matching object in Cerebrum (if available) and call
        `sync_object(mapped-data, cerebrum-object)` to start the actual sync.
        """
        reference = raw_data['id']
        hr_object = self.mapper.translate(reference, raw_data)

        try:
            db_object = self.find_entity(hr_object)
        except ValueError:
            # This means we definitely can't find an existing person.
            # We'll try to create one in the next step, but it'll fail as we
            # don't have any valid identifiers...
            logger.warning("No valid identifiers for hr-object=%r", hr_object)
            db_object = None

        return self.sync_object(hr_object, db_object)

    def sync_object(self, hr_object, db_object):
        """
        Sync hr-object with given database-object.

        This method inspects and compares the source data and cerebrum data,
        and calls the relevant create/update/remove method.

        :type hr_object: HrPerson
        :type db_object: Cerebrum.Person.Person
        """
        retry_dates = self.mapper.needs_delay(hr_object)
        if not hr_object:
            raise DatasourceInvalid('hr_object is empty')

        db_id = db_object.entity_id if db_object else None

        is_active = self.mapper.is_active(hr_object)
        logger.debug('sync-object: %r (active=%r) to id=%r',
                     hr_object, is_active, db_id)

        is_deceased = (
            db_object
            and db_object.deceased_date
            and (date_compat.get_date(db_object.deceased_date)
                 < datetime.date.today()))
        if is_deceased:
            logger.warning('sync-object: id=%r is marked as deceased', db_id)

        if is_active and not is_deceased:
            if db_object:
                logger.info('sync-object: updating id=%r from %r',
                            db_id, hr_object)
                self.update(hr_object, db_object)
            else:
                logger.info('sync-object: creating new db-object from %r',
                            hr_object)
                self.create(hr_object)
        elif db_object:
            logger.info('sync-object: removing id=%r from %r',
                        db_object.entity_id, hr_object)
            self.remove(hr_object, db_object)
        else:
            logger.info('sync-object: nothing to do for %r', hr_object)

        if retry_dates:
            logger.debug('sync-object: needs delay, retry at %r',
                         retry_dates)
        return retry_dates

    @abc.abstractmethod
    def create(self, hr_object):
        """ Create a new Cerebrum object from the source data. """
        pass

    @abc.abstractmethod
    def update(self, hr_object, db_object):
        """ Update an existing Cerebrum object from the source data. """
        pass

    @abc.abstractmethod
    def remove(self, hr_object, db_object):
        """ Remove source data from an existing Cerebrum object. """
        pass


def get_retries(retry_dates):
    """ Convert retry_dates to datetime objcets.

    :param retry_dates: iterable of local timestamps

    :return: sorted list of tz-aware datetime objects
    """
    # `retries` is currently a set of unix timestamp strings - we should
    # probably change this to a sorted tuple of datetime.date[time] objects.
    def _iter_retries(date_list):
        for date_like in (date_list or ()):
            try:
                yield date_compat.get_datetime_tz(date_like)
            except OverflowError:
                # happens if the date_like is close to datetime.MAXYEAR, and tz
                # conversion put it out of bounds.  This is not a retry date
                # that is interesting to keep.
                continue

    return sorted(_iter_retries(retry_dates))


def get_next_retry(retry_dates, cutoff=None):
    """ Find the next retry from a set of retry dates.

    :param retry_dates:
        iterable of date-like objects

    :param cutoff:
        only consider retry_dates after this datetime (defaults to now)

    :rtype: datetime.datetime, NoneType
    :return:
        the next retry time, or None if ``retry_dates`` does not contain a
        valid retry time
    """
    # Ignore retries in the past - they would just cause an immediate second
    # import task, which would end up processing the same set of data.
    start_cutoff = cutoff or now()

    # Ignore retries after this hard-coded date - these tasks would just be too
    # ridiculously far into the future to be viable.
    #
    # This filtering could (should?) probably be moved into the hr-system
    # specific parts of the import (i.e. treat certain far-into-the-future
    # start/end dates as being omitted), but it's so much easier to just filter
    # them out here.
    end_cutoff = datetime.date(2200, 1, 1)

    for retry in get_retries(retry_dates):
        if retry > start_cutoff and retry.date() < end_cutoff:
            return retry
