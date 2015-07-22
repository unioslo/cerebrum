#!/usr/bin/env python
# encoding: utf-8
u"""Application bootstrap"""

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
from database import Database
from auth import Authentication

db = Database()
auth = Authentication()

import api.v1


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config['RESTFUL_JSON'] = {'ensure_ascii': False, 'encoding': 'utf-8'}
    app.wsgi_app = ProxyFix(app.wsgi_app)

    app.register_blueprint(api.v1.blueprint, url_prefix='/v1')

    db.init_app(app)
    auth.init_app(app, db)

    if app.debug:
        from flask import g, request
        import time

        @app.before_request
        def before_request():
            g.start = time.time()

        @app.teardown_request
        def teardown_request(exception=None):
            diff = time.time() - g.start
            millis = int(round(diff * 1000))
            print 'Spent', millis, 'ms serving', request.full_path

    return app
