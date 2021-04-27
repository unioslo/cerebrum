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
""" Tasks related to the SAPUiO hr-import.  """
import logging

from Cerebrum.modules.hr_import.importer import get_next_retry
from Cerebrum.modules.tasks import process
from Cerebrum.modules.tasks import task_models
from Cerebrum.utils.date import now
from .datasource import parse_message

logger = logging.getLogger(__name__)


class EmployeeTasks(process.QueueHandler):

    queue = 'sap-legacy'

    manual_sub = 'manual'
    nbf_sub = 'nbf'

    max_attempts = 20

    def __init__(self, get_import):
        self.get_import = get_import

    def handle_task(self, db, dryrun, task):
        do_import = self.get_import(db).handle_reference
        next_retry = get_next_retry(do_import(task.payload.data['id']))

        if next_retry:
            # import discovered a start date or end date to be processed
            # later
            return task_models.Task(
                queue=self.queue,
                sub=self.delay_sub,
                key=task.key,
                nbf=next_retry,
                reason='next-change: on={when}'.format(when=next_retry),
                payload=task.payload)
        else:
            return None

    @classmethod
    def create_manual_task(cls, reference):
        """ Create a manual task. """
        payload = task_models.Payload(
            fmt='sap-legacy-event',
            version=1,
            data={'id': reference},
        )
        return task_models.Task(
            queue=cls.queue,
            sub=cls.manual_sub,
            key=reference,
            attempts=0,
            reason='manual: on={when}'.format(when=now()),
            payload=payload,
        )


def get_tasks(event):
    """ Get tasks from a consumer event.

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
    queue = EmployeeTasks.queue
    sub = None

    if is_delayed:
        sub = EmployeeTasks.nbf_sub

    yield task_models.Task(
        queue=queue,
        sub=sub,
        key=fields['id'],
        nbf=fields['nbf'],
        reason='event: ex={ex} rk={rk} jti={jti} on={when}'.format(
            ex=event.method.exchange,
            rk=event.method.routing_key,
            jti=fields['jti'],
            when=str(now()),
        ),
        attempts=0,
        # NOTE: Rememeber to bump the version if *any* changes are made to this
        # data structure!
        payload=task_models.Payload(
            fmt='sap-legacy-event',
            version=1,
            data={'id': fields['id']},
        ),
    )
