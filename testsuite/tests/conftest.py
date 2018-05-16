#!/usr/bin/env python
# encoding: utf-8
u""" Global py-test config and fixtures.

This module contains fixtures that should be shared across all tests.
"""
import pytest
import types
import cerebrum_path


@pytest.fixture
def cereconf():
    u""" 'cereconf' config.

    This fixture allows test modules to change cereconf settings when certain
    settings need to be tested, or when certain changes needs to be injected in
    the config.
    """
    try:
        import cereconf
        return cereconf
    except ImportError:
        pytest.xfail(u"Unable to import 'cereconf'")


@pytest.fixture
def factory(cereconf):
    u""" `Cerebrum.Utils.Factory`.

    We list cereconf as a 'dependency' in order to have it processed before
    importing and using the factory.
    """
    from Cerebrum.Utils import Factory
    return Factory


@pytest.fixture
def logger(factory):
    # TODO: Get a dummy logger that doesn't depend on logging.ini?
    return factory.get_logger('console')


@pytest.yield_fixture
def database(factory):
    u"""`Cerebrum.database.Database` with automatic rollback."""
    db = factory.get('Database')()
    db.commit = db.rollback
    print 'database init', db, db._cursor
    yield db
    print 'database rollback', db, db._cursor
    db.rollback()


@pytest.fixture
def constant_module(database):
    u""" Patched `Cerebrum.Constants` module.

    This fixture patches the _CerebrumCode constants, so that they use the same
    database transaction as the `database` fixture.

    It also patches each _CerebrumCode subclass, so that the constant cache is
    cleared for each scope.

    """
    from Cerebrum import Constants as module
    # Patch the `sql` property to always return a known db-object
    module._CerebrumCode.sql = property(lambda *args: database)
    # Clear the constants cache of each _CerebrumCode class, to avoid caching
    # intvals that doesn't exist in the database.
    for item in vars(module).itervalues():
        if (isinstance(item, (type, types.ClassType))
                and issubclass(item, module._CerebrumCode)):
            item._cache = dict()
    return module


@pytest.fixture
def initial_account(database, factory, cereconf):
    ac = factory.get('Account')(database)
    ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    return ac


@pytest.fixture
def initial_group(database, factory, cereconf):
    gr = factory.get('Group')(database)
    gr.find_by_name(cereconf.INITIAL_GROUPNAME)
    return gr
