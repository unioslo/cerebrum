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
Tasks related to the Greg guest import.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.modules.tasks import queue_handler
from Cerebrum.modules.tasks import task_models
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import mime_type

from .datasource import parse_message


logger = logging.getLogger(__name__)


class GregImportTasks(queue_handler.QueueHandler):
    """ This object defines the 'greg-person' task queues. """

    queue = 'greg-person'
    manual_sub = 'manual'
    max_attempts = 20

    def __init__(self, client, import_class):
        self._client = client
        self._import_class = import_class

    def _callback(self, db, task):
        greg_id = task.key
        logger.info('Updating greg_id=%s', greg_id)
        importer = self._import_class(db, client=self._client)
        importer.handle_reference(greg_id)
        logger.info('Updated greg_id=%s', greg_id)

        # TODO: Should we have the importer return potential new tasks?  If so,
        # we could rely on the default *handle_task* implementation for
        # re-queueing.
        #
        # *Or* should the import itself add potential tasks to the queue?  It
        # kind of depends on whether we want the option to run the importer
        # *without* adding new tasks to the queue...
        return []

    @classmethod
    def create_manual_task(cls, reference, sub=manual_sub, nbf=None):
        """ Create a manual task. """
        return task_models.Task(
            queue=cls.queue,
            sub=sub,
            key=reference,
            nbf=nbf,
            attempts=0,
            reason='manually added',
        )


def get_tasks(event):
    """
    Get tasks from a consumer event.

    :type db: Cerebrum.database.Database
    :type event: Cerebrum.modules.amqp.handler.Event

    :rtype: generator
    :returns:
        zero or more :class:`Cerebrum.modules.task.task_models.Task`
        objects
    """
    try:
        # greg uses `content-type: application/json`, which should default to
        # utf-8
        charset = mime_type.get_charset(event.content_type, default="utf-8")
        json_data = event.body.decode(charset)
        fields = parse_message(json_data)
    except Exception:
        logger.error('invalid event: %s', repr(event), exc_info=True)
        return

    msg_id = fields['id']
    person_id = fields['data'].get('person_id')

    # TODO: Should we examine `fields['type']` and only yield tasks for
    #       type="person.*"?
    if not person_id:
        logger.info('ignoring event id=%s, missing person_id', msg_id)
        return

    yield task_models.Task(
        queue=GregImportTasks.queue,
        sub=None,
        key=person_id,
        reason='event: id={id} ex={ex} rk={rk} tag={ct}'.format(
            id=msg_id,
            ex=event.method.exchange,
            rk=event.method.routing_key,
            ct=event.method.consumer_tag,
        ),
        # Explicit defaults, to ensure we replace old values
        attempts=0,
        nbf=date_utils.now(),
    )
