#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2017 University of Oslo, Norway
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
""" Celery scheduler app. """
import json
from contextlib import contextmanager
from celery.utils.log import get_task_logger

from Cerebrum.modules.celery_tasks import create_celery_app
from Cerebrum.modules.event_publisher import get_client
from Cerebrum.modules.event_publisher.config import load_publisher_config


app = create_celery_app('scheduler')


@contextmanager
def exception_logger(logger, action=None):
    action = ' ({0})'.format(action) if action else ''
    try:
        yield
    except Exception as e:
        logger.error("{0}: {1}{2}".format(type(e), e, action))
        raise


@app.task(bind=True,
          name='scheduler.schedule_message',
          max_retries=None,
          default_retry_delay=30 * 60)  # retries every 30mins
def schedule_message(self, routing_key, body):
    """
    Keyword Arguments:
    :param routing_key: Routing key for the topic exchange
    :type routing_key: str or unicode

    :param body: Message body in json.dumps format
    :type body: str
    """
    logger = get_task_logger(__name__)
    try:
        with exception_logger(logger):
            message = json.loads(body)
            config = load_publisher_config('schedule_message')
            print config.exchange_name
            publisher_client = get_client(config)
            with publisher_client as client:
                client.publish(routing_key, message)
                logger.info(
                    'Message published (jti={0})'.format(message.get('jti')))

    except Exception as e:
        # we want to log and retry sending indefinitely...
        # TODO logger... use Cerebrum's??
        raise self.retry(exc=e, max_retries=None)  # retry forever


if __name__ == '__main__':
    app.start()
