#!/usr/bin/env python
# encoding: utf-8
u""" Global py-test config and fixtures.

This module contains fixtures that should be shared across all tests.
"""
import pytest
import types


@pytest.fixture
def factory():
    u""" `Cerebrum.Utils.Factory` """
    return getattr(pytest.importorskip('Cerebrum.Utils'), 'Factory')


@pytest.fixture
def logger(factory):
    # TODO: Get a dummy logger that doesn't depend on logging.ini?
    return factory.get_logger('console')


@pytest.yield_fixture
def database(factory):
    u""" `Cerebrum.Database` with automatic rollback. """
    db = factory.get('Database')()
    db.commit = db.rollback
    print 'db init', db, db._cursor
    yield db
    print 'db rollback', db, db._cursor
    db.rollback()


@pytest.fixture
def constant_module(database):
    u""" Patched `Cerebrum.Constants` module.

    This fixture patches the _CerebrumCode constants, so that they use the same
    database transaction as the `database` fixture.

    It also patches each _CerebrumCode subclass, so that the constant cache is
    cleared for each scope.

    """
    module = pytest.importorskip("Cerebrum.Constants")
    # Patch the `sql` property to always return a known db-object
    module._CerebrumCode.sql = property(lambda *args: database)
    # Clear the constants cache of each _CerebrumCode class, to avoid caching
    # intvals that doesn't exist in the database.
    for item in vars(module).itervalues():
        if (isinstance(item, (type, types.ClassType))
                and issubclass(item, module._CerebrumCode)):
            item._cache = dict()
    return module
