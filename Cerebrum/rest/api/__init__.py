#!/usr/bin/env python
# encoding: utf-8
u"""Application bootstrap"""

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
from flask import g, request
import time
import logging
import logging.config as log_config
from database import Database
from auth import Authentication

db = Database()
auth = Authentication()


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config['RESTFUL_JSON'] = {'ensure_ascii': False, 'encoding': 'utf-8'}
    app.wsgi_app = ProxyFix(app.wsgi_app)
    logger = logging.getLogger(config.LOGGER_NAME)

    import api.v1
    app.register_blueprint(api.v1.blueprint, url_prefix='/v1')
    db.init_app(app)
    auth.init_app(app, db)
    log_config.dictConfig(config.LOGGING)

    @app.before_request
    def before_request():
        g.start = time.time()

    @app.after_request
    def log_request_data(response):
        req_time = time.time() - g.start
        req_time_millis = int(round(req_time * 1000))

        if g.get('user'):
            logger.debug('"{method} {path} - {code}" -  User: {user}, '
                         'Auth: {auth}, IP: {ip}, UA: {ua}, '
                         'Req took: {req_time}ms.'.format(
                            method=request.method,
                            path=request.path,
                            code=response.status_code,
                            user=g.get('user'),
                            auth=g.get('auth'),
                            ip=request.remote_addr,
                            ua=request.user_agent,
                            req_time=req_time_millis))
        else:
            logger.debug('"{method} {path} - {code}" - IP: {ip}, UA: {ua}, '
                         'Req took: {req_time}ms.'.format(
                            method=request.method,
                            path=request.path,
                            code=response.status_code,
                            ip=request.remote_addr,
                            ua=request.user_agent,
                            req_time=req_time_millis))
        return response
    return app
