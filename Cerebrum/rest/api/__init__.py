#!/usr/bin/env python
# encoding: utf-8
u"""Application bootstrap"""
from __future__ import absolute_import

import logging
import logging.config
import time
from flask import Flask, g, request
from werkzeug.contrib.fixers import ProxyFix
from .database import Database
from .auth import Authentication

db = Database()
auth = Authentication()


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config['RESTFUL_JSON'] = {'ensure_ascii': False, 'encoding': 'utf-8'}
    app.wsgi_app = ProxyFix(app.wsgi_app)
    logging.config.dictConfig(app.config['LOGGING'])

    from Cerebrum.rest.api import v1
    app.register_blueprint(v1.blueprint, url_prefix='/v1')

    db.init_app(app)
    auth.init_app(app, db)

    @app.before_request
    def register_request_start():
        g.request_start = time.time()

    @app.after_request
    def log_request_data(response):
        req_time = time.time() - g.request_start
        req_time_millis = int(round(req_time * 1000))

        app.logger.info('"{method} {path}" - {code} - {req_time}ms - {auth} - '
                        '{ip} - "{ua}"'.format(
                            method=request.method,
                            path=request.full_path,
                            code=response.status_code,
                            auth=str(auth._module),
                            ip=request.remote_addr,
                            ua=request.user_agent,
                            req_time=req_time_millis))
        return response
    return app
