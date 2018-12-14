#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

"""Application bootstrap"""

from __future__ import absolute_import, unicode_literals

import logging
import logging.config
import time

from flask import Flask, g, request
from werkzeug.contrib.fixers import ProxyFix
from six import text_type

from . import database as _database
from . import auth as _auth
from .routing import NormalizedUnicodeConverter


db = _database.DatabaseContext()
auth = _auth.Authentication()


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object('Cerebrum.rest.default_config')
    if config:
        app.config.from_object(config)
        trusted_hosts = app.config.get('TRUSTED_HOSTS', [])

    app.config['RESTFUL_JSON'] = {'ensure_ascii': False, 'encoding': 'utf-8'}
    app.wsgi_app = ProxyFix(app.wsgi_app)
    logging.config.dictConfig(app.config['LOGGING'])

    # As of Flask 0.11, Flask sets up a logger by itself, logging to stderr.
    # Add handlers from '' logger to log here, too.
    logger = logging.getLogger('')
    for handler in logger.handlers:
        app.logger.addHandler(handler)

    # Replace builtin URL rule converters. Must be done before rules are added.
    app.url_map.converters.update({
        'default': NormalizedUnicodeConverter,
        'string': NormalizedUnicodeConverter,
    })

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

        ip_log = [i for i in request.access_route]
        for ip in ip_log:
            if trusted_hosts:
                if ip in trusted_hosts:
                    ip_log.pop(ip_log.index(ip))

        app.logger.info('"{method} {path}" - {code} - {req_time}ms - {auth} - '
                        '{ip} - "{ua}"'.format(
                            method=request.method,
                            path=request.full_path,
                            code=response.status_code,
                            auth=text_type(auth.ctx.module),
                            ip=ip_log,
                            ua=request.user_agent,
                            req_time=req_time_millis))
        return response
    return app
