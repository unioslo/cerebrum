# -*- coding: utf-8 -*-

from celery import Celery

from Cerebrum.Utils import read_password
from Cerebrum.config.loader import read, read_config
from Cerebrum.modules.event_publisher.config import AMQPClientPublisherConfig


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
    app.conf['broker_url'] = app.conf['result_backend'] = broker_url
    # deprecated Celery 3.x format...
    app.conf['BROKER_URL'] = app.conf['CELERY_RESULT_BACKEND'] = broker_url
    return app


def load_amqp_client_config(celery_task, filepath=None):
    """
    Loads the Cerebrum.config for the AMQPClient

    defaults to sys.prefix/etc/config/`celery_task`.json
    """
    config = AMQPClientPublisherConfig()
    if filepath:
        config.load_dict(read_config(filepath))
    else:
        read(config, celery_task)
    config.validate()
    return config
