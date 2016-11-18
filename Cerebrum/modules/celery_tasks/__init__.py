# -*- coding: utf-8 -*-

from Cerebrum.Utils import read_password

from celery import Celery


def create_celery_app(app_name):
    """
    Creates a celery.Celery (app) object with the name `app_name`
    and uses the config object `app_name`

    Keyword Arguments:
    :param app_name: The name of the app and the setting module-object
    :type app_name: str

    :return: celery.Celery (app) object
    :rtype: celery.Celery
    """
    app = Celery(app_name)
    app.config_from_object(app_name)
    broker_url = ('amqp://{username}:{password}@'
                  '{hostname}:{port}/{vhost}').format(
                      username=app.conf['CELERY_TASKS_USERNAME'],
                      password=read_password(
                          app.conf['CELERY_TASKS_USERNAME'],
                          app.conf['CELERY_TASKS_HOSTNAME']),
                      hostname=app.conf['CELERY_TASKS_HOSTNAME'],
                      port=app.conf['CELERY_TASKS_PORT'],
                      vhost=app.conf['CELERY_TASKS_VHOST'])
    app.conf['BROKER_URL'] = broker_url
    return app
