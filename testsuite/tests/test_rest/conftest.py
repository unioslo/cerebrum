#!/usr/bin/env python
# encoding: utf-8
u""" Global py-test config and fixtures.

This module contains fixtures that should be shared across all tests.
"""
import pytest


@pytest.fixture
def app():
    from flask import Flask
    app_ = Flask('unittest')
    return app_


@pytest.fixture
def db_ctx(app, database):
    u""" DatabaseContext. """
    from Cerebrum.rest.api import database as _db_module
    _db_module._connect = lambda: database
    return _db_module.DatabaseContext(app)


@pytest.yield_fixture
def app_ctx(app):
    with app.app_context() as ctx:
        yield ctx
