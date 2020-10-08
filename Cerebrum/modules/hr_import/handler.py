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
HR import handlers (for use with :mod:`Cerebrum.modules.amqp.consumer`
"""
import contextlib
import logging

from Cerebrum.modules.amqp.handlers import AbstractConsumerHandler

from .datasource import DatasourceInvalid, DatasourceUnavailable
from .mapper import MapperError

logger = logging.getLogger(__name__)


class DatabaseConflict(RuntimeError):
    """ Unable to import data due to conflict. """
    pass


@contextlib.contextmanager
def db_context(init_db, dryrun):
    """ A database context manager. """
    db = init_db()
    try:
        logger.debug('db_context: enter dryrun=%r, db=%r, conn=%r',
                     dryrun, db, db._db)
        yield db
    except Exception as e:
        logger.warning('db_context: rollback (unhandled exception=%r)', e)
        db.rollback()
        raise

    if dryrun:
        logger.info('db_context: rollback (dryrun)')
        db.rollback()
    else:
        logger.info('db_context: commit')
        db.commit()


class EmployeeHandler(AbstractConsumerHandler):
    """ Handle HR person events. """

    def __init__(self, task_mapper, db_init, dryrun, importer_config=None):
        """
        :type task_mapper: Cerebrum.modules.amqp.mapper.MessageToTaskMapper
        :param task_mapper:
            Mapper used for mapping an incoming event to the appropriate
            importer_class.

        :param db_init:
            Database factory.  Should take no arguments and return a
            :class:`Cerebrum.database.Database` object.

        :param dryrun: True if all changes should be rolled back

        :type importer_config:
            Cerebrum.modules.no.uio.importer.EmployeeImportConfig

        """
        # Validate importer config
        for task in task_mapper.tasks:
            task.call(None, importer_config)

        self.task_mapper = task_mapper
        self.db_init = db_init
        self.dryrun = dryrun
        self.importer_config = importer_config

    def handle(self, event):
        logger.debug('processing change for event=%r', event)

        for call in self.task_mapper.message_to_callable(event):
            with db_context(self.db_init, self.dryrun) as db:
                importer = call(db, self.importer_config)
                importer.handle_event(event)

    def on_error(self, event, error):
        # TODO: Separate between DatasourceInvalid, DatasourceUnavailable
        #       The latter should cause a re-queue and pause/backoff
        #       message processing
        if isinstance(error, DatasourceUnavailable):
            logger.warning('unable to fetch event=%r: %r', event, error)
        elif isinstance(error, DatasourceInvalid):
            logger.error('unable to fetch event=%r: %r', event, error)
        elif isinstance(error, MapperError):
            logger.error('unable to import event=%r: %s', event, error)
        return False
