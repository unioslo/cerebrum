# -*- coding: utf-8 -*-

from Cerebrum.modules.celery_tasks import create_celery_app

app = create_celery_app('scheduler')


@app.task(bind=True, name='scheduler.schedule_AD_message')
def schedule_AD_message(self, message):
    """
    Keyword Arguments:
    :param message:
    :type message:

    """
    pass
