# -*- coding: utf-8 -*-

from Cerebrum.modules.celery_tasks import create_celery_app

app = create_celery_app('scheduler')
