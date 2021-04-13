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
""" Queue processing utils.  """
import datetime
import logging

from Cerebrum.utils import backoff
from Cerebrum.utils.date import now
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import task_queue

logger = logging.getLogger(__name__)


def copy_task(task):
    return task_models.Task.from_dict(task.to_dict())


delay_on_error = backoff.Backoff(
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
    nbf_queue = None

    # queue for re-queueing failed tasks
    # defaults to the same queue as regular tasks
    retry_queue = None

    # delay queue for tasks if we discover a future date during handling
    # defaults to the same queue as regular tasks
    delay_queue = None

    # extra queue for tasks that were added manually
    manual_queue = None

    # when to give up on a task
    max_attempts = 20

    @property
    def all_queues(self):
        """ queues with tasks for this handler. """
        return tuple(
            q for q in (self.queue, self.nbf_queue, self.retry_queue,
                        self.delay_queue, self.manual_queue)
            if q)

    def get_retry_task(self, task, error):
        """ Create a retry task from a failed task. """
        retry = copy_task(task)
        retry.queue = self.retry_queue or self.queue
        retry.attempts = task.attempts + 1
        retry.nbf = now() + delay_on_error(task.attempts + 1)
        retry.reason = 'retry: failed_at={} error={}'.format(now(), error)
        return retry

    def handle_task(self, db, dryrun, task):
        """ Task implementation. """
        raise NotImplementedError('abstract method')

    def __call__(self, db, dryrun, task):
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
        next_task = self.handle_task(db, dryrun, task)
        if next_task and task_queue.TaskQueue(db).push(next_task,
                                                       ignore_nbf_after=True):
            logger.info('queued next-task %s/%s at %s',
                        next_task.queue, next_task.key, next_task.nbf)
