# -*- coding: utf-8 -*-

from Cerebrum.modules.celery_tasks import create_celery_app

app = create_celery_app('scheduler')


@app.task(bind=True, name='scheduler.schedule_message')
def schedule_message(self, exchange, routing_key, body):
    """
    Keyword Arguments:
    :param exchange: Topic exchange to use
    :type exchange: str or unicode

    :param routing_key: Routing key for the topic exchange
    :type routing_key: str or unicode

    :param body: Message body in json.dumps format
    :type body: str
    """
    pass


if __name__ == '__main__':
    app.start()
