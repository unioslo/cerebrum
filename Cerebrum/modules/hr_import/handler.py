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

    def __init__(self, import_init, db_init, dryrun):
        """
        :type datasource: .datasource.AbstractDatasource
        :param datasource: A datasource implementation

        :param import_init:
            Import factory.  Should take a single database-argument and return
            a :class:`.importer.AbstractImport` object.

        :param db_init:
            Database factory.  Should take no arguments and return a
            :class:`Cerebrum.database.Database` object.

        :param dryrun: True if all changes should be rolled back
        """
        self.import_init = import_init
        self.db_init = db_init
        self.dryrun = dryrun

    def handle(self, event):
        logger.debug('processing change for event=%r', event)

        with db_context(self.db_init, self.dryrun) as db:
            importer = self.import_init(db)
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
