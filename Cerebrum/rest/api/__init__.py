#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""Application bootstrap"""

from __future__ import absolute_import, unicode_literals

import logging
import logging.config
import time

from flask import Flask, g, request
from werkzeug.contrib.fixers import ProxyFix
from . import database as _database
from . import auth as _auth


db = _database.DatabaseContext()
auth = _auth.Authentication()


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config['RESTFUL_JSON'] = {'ensure_ascii': False, 'encoding': 'utf-8'}
    app.wsgi_app = ProxyFix(app.wsgi_app)
    logging.config.dictConfig(app.config['LOGGING'])

    # As of Flask 0.11, Flask sets up a logger by itself, logging to stderr.
    # Add handlers from '' logger to log here, too.
    logger = logging.getLogger('')
    for handler in logger.handlers:
        app.logger.addHandler(handler)

    from Cerebrum.rest.api import v1
    app.register_blueprint(v1.blueprint, url_prefix='/v1')

    @app.before_request
    def register_request_start():
        g.request_start = time.time()

    db.init_app(app)
    auth.init_app(app, db)

    @app.after_request
    def log_request_data(response):
        req_time = time.time() - g.request_start
        req_time_millis = int(round(req_time * 1000))

        app.logger.info('"{method} {path}" - {code} - {req_time}ms - {auth} - '
                        '{ip} - "{ua}"'.format(
                            method=request.method,
                            path=request.full_path,
                            code=response.status_code,
                            auth=str(auth.ctx.module),
                            ip=request.remote_addr,
                            ua=request.user_agent,
                            req_time=req_time_millis))
        return response
    return app
