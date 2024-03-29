# -*- coding: utf-8 -*-
#
# Copyright 2021-2023 University of Oslo, Norway
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
""" Queue processing utils.  """
import datetime
import logging

from Cerebrum.utils import backoff
from Cerebrum.utils.date import now
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import task_queue

logger = logging.getLogger(__name__)


# Default backoff for errors/retries in QueueHandler.  This backoff yields
# time deltas 03:45, 07:30, 15:00, 30:00, 1:00:00, ... - before truncating at
# 12:00:00 after 10 attempts.  This should be a good backoff for most tasks.
default_retry_delay = backoff.Backoff(
    backoff.Exponential(2),
    backoff.Factor(datetime.timedelta(hours=1) / 16),
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
