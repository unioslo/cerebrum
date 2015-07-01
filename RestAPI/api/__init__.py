#!/usr/bin/env python
# encoding: utf-8
u"""Application bootstrap"""

from flask import Flask
from database import Database
from auth import Authentication

db = Database()
auth = Authentication()

import api.v1


def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)

    app.register_blueprint(api.v1.blueprint, url_prefix='/v1')

    db.init_app(app)
    auth.init_app(app, db)

    return app
