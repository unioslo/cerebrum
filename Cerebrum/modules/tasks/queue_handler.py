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
Queue handler.

Tasks are intended for automatic processing, and all tasks in a given task
queue should always be processed by the same set of operations.

The QueueHandler is an object to connect queues, tasks and processing
operations.  The abstract handler defined in this module is more of a
*suggestion* than default implementation.

A couple of things should *always* be present in a QueueHandler:

``QueueHandler.queue``
    A queue to process.  This class attribute should be available to scripts
    and modules to identify tasks that belongs to this QueueHandler.

``QueueHandler.handle_task``
    The default task handler.  The handler shuuld perform all neccessary
    actions to handle a given task.  It expects a task object that has been
    popped (fetched and removed) from the database.
    Note that ``handle_task`` should *not* handle failures - this is up to the
    caller to deal with.

``QueueHandler.get_retry_task``
    Create a new retry task for a failed task.  The queue handler defines how
    these retry tasks should look (e.g. which sub-queue they should be placed
    in, how long the retry delay should be, etc...)

``QueueHandler.max_attempts``
    Max number of attempts before we abandon a task and stop processing it.

Note that the task queue and task processors are maybe the least thought out
parts of the task module.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging

from Cerebrum.utils import backoff
from Cerebrum.utils.date import now
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import task_queue

logger = logging.getLogger(__name__)


# Default backoff for errors/retries in QueueHandler.  This backoff yields
# time deltas 03:45, 07:30, 15:00, 30:00, 1:00:00, ... - before truncating at
# 12:00:00 after 9 attempts.  This should be a good backoff for most tasks:
#  - 1st retry in less than 5 minutes, 2nd ~10 minutes after the initial
#  - about an hour to reach 4 failed attempts
#  - just under two days to reach 10 failed attempts
#  - just under one week to reach 20 failed attempts
default_retry_delay = backoff.Backoff(
    backoff.Exponential(2),
    backoff.Factor(datetime.timedelta(hours=1) // 16),
    backoff.Truncate(datetime.timedelta(hours=12)),
)


class QueueHandler(object):
    """ Processing rules and task implementation for a given set of queues. """

    # queue for adding regular tasks
    queue = 'example'

    # queue for adding tasks with a future nbf date
    # defaults to *queue*
    nbf_sub = None

    # queue for re-queueing failed tasks
    # defaults to the same queue as regular tasks
    retry_sub = None

    # delay queue for tasks if we discover a future date during handling
    # defaults to the same queue as regular tasks
    delay_sub = None

    # extra queue for tasks that were added manually
    manual_sub = None

    # when to give up on a task
    max_attempts = 20

    # next delay (timedelta) after *n* failed attempts
    get_retry_delay = default_retry_delay

    def __init__(self, callback):
        self._callback = callback

    def get_retry_task(self, task, error):
        """ Create a retry task from a failed task. """
        retry = task_models.copy_task(task)
        retry.queue = self.queue
        retry.sub = self.retry_sub or task.sub
        retry.attempts = task.attempts + 1
        retry.nbf = now() + self.get_retry_delay(task.attempts + 1)
        retry.reason = 'retry: failed_at={} error={}'.format(now(), error)
        return retry

    def handle_task(self, db, task):
        """
        Task processing entry point.

        :type db: Cerebrum.database.Database

        :type dryrun: bool
        :param dryrun:
            rollback changes done by the task implementation

        :type task: task_models.Task
        :param task:
            a task to process
        """
        next_tasks = self._callback(db, task)
        if next_tasks:
            task_db = task_queue.TaskQueue(db)
            for next_task in next_tasks:
                if task_db.push_task(next_task):
                    logger.info('queued next-task %s/%s/%s at %s',
                                next_task.queue, next_task.sub,
                                next_task.key, next_task.nbf)

    def get_queue_counts(self, db, **kwargs):
        """ Get number of tasks by (queue, sub). """
        if 'queues' in kwargs:
            raise TypeError("get_queue_counts() got an unexpected keyword "
                            "argument 'queues'")
        for row in task_queue.sql_get_subqueue_counts(db, queues=self.queue,
                                                      **kwargs):
            yield (row['queue'], row['sub']), row['num']

    def get_abandoned_counts(self, db):
        """ Get number of abandoned tasks by (queue, sub). """
        for qs, count in self.get_queue_counts(db,
                                               min_attempts=self.max_attempts):
            if count > 1:
                yield qs, count
