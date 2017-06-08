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
""" Celery app. """
from celery import Celery

from Cerebrum.Utils import read_password


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
    app.conf['broker_url'] = broker_url
    # deprecated Celery 3.x format...
    app.conf['BROKER_URL'] = broker_url
    return app
