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

from .mapper import NoMappedObjects

logger = logging.getLogger(__name__)


class AbstractImport(object):

    def __init__(self, db):
        self.db = db

    @abc.abstractproperty
    def datasource(self):
        """ A datasource to use for fetching HR data. """
        pass

    @abc.abstractproperty
    def mapper(self):
        """ A mapper to use for translating HR data to Cerebrum. """
        pass

    def handle_event(self, event):
        """
        Initiate hr import from event.

        This is the entrypoint for use with a Cerebrum.modules.amqp handler.
        Fetches external reference from event and calls handle_reference.

        :param event:
            A Cerebrum.modules.amqp event
        """
        reference = self.datasource.get_reference(event)
        self.handle_reference(reference)

    def handle_reference(self, reference):
        """
        Initiate hr import from reference.

        This is the entrypoint for use with e.g. scripts.
        Fetches object data from the datasource and calls handle_object.
        """
        raw_data = self.datasource.get_object(reference)
        hr_object = self.mapper.translate(reference, raw_data)

        try:
            db_object = self.mapper.find_entity(hr_object)
        except NoMappedObjects:
            db_object = None

        self.handle_object(hr_object, db_object)

    def handle_object(self, hr_object, db_object):
        """
        Initiate hr import.

        This method inspects and compares the source data and cerebrum data,
        and calls the relevant create/update/remove method.
        """
        # TODO: Fixme! Should we look at the raw data or the hr_object to
        #       figure out if the object should be present?!
        if self.mapper.is_active(hr_object):
            if db_object:
                logger.info('updating id=%r with %r',
                            db_object.entity_id, hr_object)
                self.update(hr_object, db_object)
            else:
                logger.info('creating %r', hr_object)
                self.create(hr_object)
        elif db_object:
            logger.info('removing id=%r (%r)',
                        db_object.entity_id, hr_object)
            self.remove(db_object)
        else:
            logger.info('nothing to do for %r', hr_object)

    @abc.abstractmethod
    def create(self, hr_object):
        """ Create a new Cerebrum object from the source data. """
        pass

    @abc.abstractmethod
    def update(self, hr_object, db_object):
        """ Update an existing Cerebrum object from the source data. """
        pass

    @abc.abstractmethod
    def remove(self, db_object):
        """ Remove source data from an existing Cerebrum object. """
        pass
