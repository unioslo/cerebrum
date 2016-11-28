# -*- coding: utf-8 -*-

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
        amqp_client = publisher_class(conf)
        amqp_client.publish(message)
    except Exception as e:
        # we want to log and retry sending indefinitely...
        # TODO logger... use Cerebrum's??
        raise self.retry(exc=e, max_retries=None)  # retry forever


if __name__ == '__main__':
    app.start()
