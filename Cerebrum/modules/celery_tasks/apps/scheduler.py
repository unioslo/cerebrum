# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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

import json

from Cerebrum.Utils import Factory
from Cerebrum.modules.celery_tasks import (create_celery_app,
                                           load_amqp_client_config)

app = create_celery_app('scheduler')


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
    try:
        message = json.loads(body)
        message['routing-key'] = routing_key
        conf = load_amqp_client_config('schedule_message')
        publisher_class = Factory.make_class('SchedulerPublisher',
                                             conf.publisher_class)
        with publisher_class(conf) as amqp_client:
            amqp_client.publish(message)
    except Exception as e:
        # we want to log and retry sending indefinitely...
        # TODO logger... use Cerebrum's??
        raise self.retry(exc=e, max_retries=None)  # retry forever


if __name__ == '__main__':
    app.start()
