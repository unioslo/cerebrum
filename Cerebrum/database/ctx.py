# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
import contextlib
import logging
import uuid

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def db_context(db, dryrun):
    """
    A database context manager.

    This context manager calls commit on the given database object if
    ``dryrun=False`` and the context exits successfully.

    :type db: Cerebrum.database.Database
    :param bool dryrun:
        if true, context will always rollback on exit
    """
    try:
        logger.debug('db_context: enter (dryrun=%r, db=%r, conn=%r)',
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
