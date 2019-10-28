#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Global py-test config and fixtures.

This module contains fixtures that should be shared across all tests.
"""
import pytest
from contextlib import contextmanager
from flask import appcontext_pushed, g

from Cerebrum.Errors import NotFoundError


class TestConfig(object):
    TESTING = True
    SERVER_NAME = 'localhost'
    AUTH = [
        {
            'name': 'HeaderAuth',
            'header': 'X-API-Key',
            'keys': {
                'foo': 'bootstrap_account',
            },
        },
    ]


@pytest.fixture
def app():
    from Cerebrum.rest.api import create_app
    app_ = create_app(TestConfig)
    return app_


@pytest.fixture
def auth_header():
    return {'X-API-Key': 'foo'}


@pytest.yield_fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.yield_fixture
def app_ctx(app):
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def db_ctx(app, app_ctx, database):
    u""" DatabaseContext. """
    from Cerebrum.rest.api import database as _db_module
    return _db_module.DatabaseContext(app)


@pytest.yield_fixture
def person_foo(db_ctx, factory):
    import datetime
    person = factory.get('Person')(db_ctx.connection)
    const = factory.get('Constants')(db_ctx.connection)
    person.populate(
        birth_date=datetime.date(2018, 1, 1),
        gender=const.gender_unknown,
        description="Person foo")
    person.write_db()
    yield person
    # teardown?


@pytest.yield_fixture
def account_foo(db_ctx, factory, initial_account, person_foo):
    account = factory.get('Account')(db_ctx.connection)
    const = factory.get('Constants')(db_ctx.connection)
    try:
        account.find_by_name('foo')
    except NotFoundError:
        pass
    account.populate(
        name='foo',
        owner_type=const.entity_person,
        owner_id=person_foo.entity_id,
        np_type=None,
        creator_id=initial_account.entity_id,
        expire_date=None,
        description="Account foo")
    account.write_db()
    yield account
    # teardown?


@pytest.yield_fixture
def group_bar(db_ctx, factory, account_foo):
    group = factory.get('Group')(db_ctx.connection)
    const = factory.get('Constants')(db_ctx.connection)
    try:
        group.find_by_name('bar')
    except NotFoundError:
        pass
    group.populate(
        name='bar',
        creator_id=account_foo.entity_id,
        expire_date=None,
        visibility=const.group_visibility_all,
        description="Group bar",
        group_type=const.group_type_unknown,
    )
    group.write_db()
    yield group
    # teardown?
