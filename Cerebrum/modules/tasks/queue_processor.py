# -*- coding: utf-8 -*-
#
# Copyright 2021-2024 University of Oslo, Norway
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
Process tasks in a task queue.

.. important::
   The py:class:`.QueueProcessor` creates and uses its own database
   object where it handles its own commit/rollback.

This module contains a py:class:`.QueueProcessor`, which handles most of the
ugliness needed to safely push/pop tasks, and commit/rollback on task
success/error.


A note on transactions
----------------------
An issue with this script is the database rollback/commit behaviour.  We would
ideally:

1. Get a *main* db-connection/transaction as argument to QueueProcessor

2. Pop task in main db-transaction (no rollback/commit at this point)

3. Execute all import changes in a sub-transaction:

   - Create savepoint
   - Run handle_tasks
   - On success: delete savepoint ('commit' to main transaction)
   - On failure: rollback to savepoint

3. On failure: Push retry-task back onto queue in main transaction

4. Commit/rollback main-transaction as needed.

This currently isn't possible, because any sub-transaction rollback *won't*
clear pending changes from ``Cerebrum.CLDatabase`` implementations.  After a
rollback, all pending (but cancelled through ``ROLLBACK TO <savepoint>``)
changes will eventually be written to changelog/audit log/event log/message log
after a main transaction commit.

Solutions:

- Change CLDatabase implementations to immediately write changes to the
  database on log_change().  This is probably the "correct" solution, and would
  also cut down on *long* commit() runtimes on large transactions.  Must make
  sure all log_change() calls are "sane" (i.e. info is available when
  log_change() runs)
- Make some insane sub-transaction context object that mimics CLDatabase, and
  runs CLDatabase.commit()/rollback() on exit (without *actually* running
  commit/rollback).  This is probably the easiest solution.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.utils.date import now

from .task_queue import TaskQueue
from .task_models import format_task_id

logger = logging.getLogger(__name__)


class QueueProcessor(object):
    """ Processes tasks according to a QueueHandler. """

    def __init__(self, queue_handler,
                 nbf_cutoff=None, limit=None, dryrun=True):
        self.queue_handler = queue_handler
        self.nbf_before = nbf_cutoff or now()
        self.limit = limit
        self._dryrun = dryrun
        self._conn = None

    @property
    def change_program(self):
        cls = type(self.queue_handler)
        return '{0.__module__}.{0.__name__}'.format(cls)

    @property
    def conn(self):
        """ database object to use. """
        if not self._conn:
            conn = Factory.get('Database')()
            conn.cl_init(change_program=self.change_program)
            self._conn = conn
        return self._conn

    def new_transaction(self):
        # "new" "transaction" - make sure no changes have been done between the
        # previous commit/rollback and this.
        return db_context(self.conn, dryrun=self._dryrun)

    def select_tasks(self, sub_queue=None):
        attempts = self.queue_handler.max_attempts
        logger.info('collecting tasks (nbf=%s, limit=%r, max-attempts=%r)',
                    self.nbf_before, self.limit, attempts)

        tasks = list(
            TaskQueue(self.conn).search_tasks(
                queues=self.queue_handler.queue,
                subs=sub_queue,
                nbf_before=self.nbf_before,
                max_attempts=attempts,
                limit=self.limit))
        self.conn.rollback()
        logger.info('found %d matching tasks', len(tasks))
        return tasks

    def process_task(self, task):
        logger.info('fetching task %s', format_task_id(task))

        # Remove the given task
        with self.new_transaction() as db:
            try:
                TaskQueue(db).pop_task(task.queue, task.sub, task.key)
            except Errors.NotFoundError:
                # we collect and process tasks in different transactions,
                # so there is a slight chance that some tasks no longer exists
                logger.error('task %s gone, already processed?',
                             format_task_id(task))
                return False

        # Process the current taask
        logger.info('handling task %s', format_task_id(task))
        try:
            with self.new_transaction() as db:
                self.queue_handler.handle_task(db, task)
            task_failed = None
        except Exception as e:
            logger.warning('task %s failed', format_task_id(task),
                           exc_info=True)
            task_failed = e

        # Re-insert the current task on error
        #
        # There is a chance that _this_ part fails, and we're unable to
        # re-insert a failed task.  Ideally, the entire task processing should
        # happen in a single transaction, while `handle_task` should use
        # savepoints to roll back if the import fails.  However, this would
        # require a rewrite of all our ChangeLog implementations...
        if task_failed:
            retry_task = self.queue_handler.get_retry_task(task, e)
            logger.info('re-queueing %s (as %s)',
                        format_task_id(task), format_task_id(retry_task))
            with self.new_transaction() as db:
                if TaskQueue(db).push_task(retry_task):
                    logger.info('queued retry-task %s at %s',
                                format_task_id(task), retry_task.nbf)

    def get_abandoned_counts(self):
        stats = self.queue_handler.get_abandoned_counts(self.conn)
        self.conn.rollback()
        return stats
