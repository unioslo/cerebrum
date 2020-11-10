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
Abstract HR import routine.

The importers binds together the datasources and mappers, and are responsible
for performing the actual database updates.
"""
import abc
import logging
import json

from .matcher import match_entity
from .mapper import NoMappedObjects
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
        """Find matching Cerebrum entity for the given HRPerson."""
        return match_entity(hr_object.external_ids,
                            self.source_system,
                            self.db)

    def handle_event(self, event):
        """
        Initiate hr import from event.

        This is the entrypoint for use with a Cerebrum.modules.amqp handler.
        Fetches external reference from event and calls handle_reference.

        :param event:
            A Cerebrum.modules.amqp event
        """
        message_body = load_message(event)
        reference = self.datasource.get_reference(message_body)
        logger.info('handle_event: valid event=%r, reference=%r',
                    event, reference)

        event_not_before = self.datasource.needs_delay(message_body)
        if event_not_before:
            # Check if the event itself has a not before date.
            # If it does, we return here and push the message to the reschedule
            # queue
            logger.info('handle_event: ignoring event with nbf=%r, event=%r',
                        event_not_before, event)
            return set([event_not_before])

        return self.handle_reference(reference)

    def handle_reference(self, reference):
        """
        Initiate hr import from reference.

        This is the entrypoint for use with e.g. scripts.
        Fetches object data from the datasource and calls handle_object.
        """
        raw_data = self.datasource.get_object(reference)
        hr_object = self.mapper.translate(reference, raw_data)

        try:
            db_object = self.find_entity(hr_object)
        except NoMappedObjects:
            db_object = None

        return self.handle_object(hr_object, db_object)

    def handle_object(self, hr_object, db_object):
        """
        Initiate hr import.

        This method inspects and compares the source data and cerebrum data,
        and calls the relevant create/update/remove method.
        """
        # TODO:
        #  Rescheduling
        retry_dates = self.mapper.needs_delay(hr_object)

        if self.mapper.is_active(hr_object):
            if db_object:
                logger.info('handle_object: updating id=%r, obj=%r',
                            db_object.entity_id, hr_object)
                self.update(hr_object, db_object)
            else:
                logger.info('handle_object: creating obj=%r', hr_object)
                self.create(hr_object)
        elif db_object:
            logger.info('handle_object: removing id=%r, obj=%r',
                        db_object.entity_id, hr_object)
            self.remove(hr_object, db_object)
        else:
            logger.info('handle_object: ignoring obj=%r', hr_object)

        if retry_dates:
            logger.debug('handle_object: needs delay, retry=%r', retry_dates)
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
