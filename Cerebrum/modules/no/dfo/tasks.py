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
""" Tasks related to the DFØ hr-import.  """
import logging

from Cerebrum.modules.hr_import.importer import get_next_retry
from Cerebrum.modules.tasks import queue_handler
from Cerebrum.modules.tasks import task_models
from Cerebrum.modules.tasks import task_queue
from Cerebrum.utils.date import now
from .datasource import parse_message

logger = logging.getLogger(__name__)


class EmployeeTasks(queue_handler.QueueHandler):

    queue = 'dfo-employee'
    manual_sub = 'manual'
    nbf_sub = 'nbf'
    max_attempts = 20

    def handle_task(self, db, task):
        """ handle an hr-import task. """
        # regular employee import returns a list of retry_date datetime values
        # we need to return a list of tasks, and we only want the first retry
        result = self._callback(db, task)
        next_retry = get_next_retry(result)

        if not next_retry:
            return
        task_db = task_queue.TaskQueue(db)
        next_task = task_db.push_task(
            task_models.Task(
                queue=self.queue,
                sub=self.delay_sub,
                key=task.key,
                nbf=next_retry,
                reason='next-change: on={when}'.format(when=next_retry),
                payload=task.payload,
            ))
        if not next_task:
            logger.info('queued next-task %s/%s/%s at %s',
                        next_task.queue, next_task.sub,
                        next_task.key, next_task.nbf)

    @classmethod
    def create_manual_task(cls, reference, sub=None, nbf=None):
        """ Create a manual task. """
        payload = task_models.Payload(
            fmt='dfo-event',
            version=1,
            data={'id': reference, 'uri': 'dfo:ansatte'})
        return task_models.Task(
            queue=cls.queue,
            sub=cls.manual_sub if sub is None else sub,
            key=reference,
            nbf=nbf,
            attempts=0,
            reason='manual: on={when}'.format(when=now()),
            payload=payload,
        )


class AssignmentTasks(queue_handler.QueueHandler):
    """
    Assignment task handler.

    Looks up assignment members, and creates EmployeeTasks for any future
    start/end date for each of them.
    """

    queue = 'dfo-assignment'
    manual_sub = 'manual'
    nbf_sub = 'nbf'
    max_attempts = 20

    def handle_task(self, db, task):
        results = self._callback(db, task)

        if not results:
            return

        task_db = task_queue.TaskQueue(db)
        for employee_id, nbf in results:
            task = EmployeeTasks.create_manual_task(
                employee_id,
                sub="",
                nbf=nbf)
            old_task = task_db.get_task(task.queue, task.sub, task.key)
            task_db.push_task(task_models.merge_tasks(task, old_task))

    @classmethod
    def create_manual_task(cls, reference):
        """ Create a manual task. """
        payload = task_models.Payload(
            fmt='dfo-event',
            version=1,
            data={'id': reference, 'uri': 'dfo:stillinger'})
        return task_models.Task(
            queue=cls.queue,
            sub=cls.manual_sub,
            key=reference,
            attempts=0,
            reason='manual: on={when}'.format(when=now()),
            payload=payload,
        )


def get_tasks(event):
    """
    Get tasks from a consumer event.

    :type db: Cerebrum.database.Database
    :type event: Cerebrum.modules.amqp.handler.Event

    :rtype: generator
    :returns:
        zero or more :py:class:`Cerebrum.modules.task.task_models.Task`
        objects to push
    """
    try:
        fields = parse_message(event.body)
    except Exception:
        logger.error('Invalid event: %s', repr(event), exc_info=True)
        return

    is_delayed = fields['nbf'] and fields['nbf'] > now()
    sub = None

    if fields['uri'] == 'dfo:ansatte':
        queue = EmployeeTasks.queue
        if is_delayed:
            sub = EmployeeTasks.nbf_sub

    elif fields['uri'] == 'dfo:stillinger':
        queue = AssignmentTasks.queue
        if is_delayed:
            sub = AssignmentTasks.nbf_sub

    else:
        logger.debug('ignoring event for uri=%s', repr(fields['uri']))
        return

    yield task_models.Task(
        queue=queue,
        sub=sub,
        key=fields['id'],
        nbf=fields['nbf'],
        reason='event: ex={ex} rk={rk} tag={ct} on={when}'.format(
            ex=event.method.exchange,
            rk=event.method.routing_key,
            ct=event.method.consumer_tag,
            when=str(now()),
        ),
        attempts=0,
        # NOTE: Rememeber to bump the version if *any* changes are made to this
        # data structure!
        payload=task_models.Payload(
            fmt='dfo-event',
            version=1,
            data={'id': fields['id'], 'uri': fields['uri']},
        ),
    )
