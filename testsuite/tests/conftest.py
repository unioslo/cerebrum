# encoding: utf-8
"""
Global py-test config and fixtures.
"""
from __future__ import print_function

import sys
import types

import pytest
import six

import Cerebrum.logutils


@pytest.fixture(autouse=True, scope='session')
def logger():
    Cerebrum.logutils._install()
    Cerebrum.logutils._configured = True
    return Cerebrum.logutils._get_legacy_logger('console')


@pytest.fixture
def cereconf():
    """ 'cereconf' config.

    This fixture allows test modules to patch cereconf settings when certain
    settings need to be tested, or when certain changes needs to be injected
    for the test to run as expected.

    To patch cereconf:

        @pytest.fixture(autouse=True)
        def _patch_foo(cereconf):
            cereconf.FOO = 3
    """
    try:
        import cereconf
        sys_remove = False
    except ImportError:
        cereconf = types.ModuleType('cereconf', 'mock cereconf module')
        sys.modules['cereconf'] = cereconf
        sys_remove = True
    # backup of initial module attributes:
    to_restore = dict(cereconf.__dict__)
    yield cereconf

    # Reset cereconf changes
    # Note: This will not reset mutations done to individual attribute values -
    # e.g. a cereconf.LDAP_PERSON.update({'foo': 'bar'})
    cereconf.__dict__.clear()
    cereconf.__dict__.update(to_restore)
    if sys_remove:
        del sys.modules['cereconf']


@pytest.fixture
def factory(cereconf):
    """ `Cerebrum.Utils.Factory`.

    We list cereconf as a 'dependency' in order to have it processed before
    importing and using the factory.
    """
    from Cerebrum.Utils import Factory
    return Factory


@pytest.fixture
def database(factory):
    """`Cerebrum.database.Database` with automatic rollback."""
    db_cls = factory.get('Database')

    class _DbWrapper(db_cls):

        def commit(self):
            print('db.commit() trapped, running db.rollback()')
            super(_DbWrapper, self).rollback()

        def rollback(self):
            print('db.rollback()')
            super(_DbWrapper, self).rollback()

        def close(self):
            print('db.close()')
            super(_DbWrapper, self).close()

    db = _DbWrapper()
    # TODO: This isn't ideal. We shouldn't use Factory to get our db driver,
    # and *really* shouldn't use a bunch of CL implementations when we run our
    # tests.  How *should* we build our db driver and ocnfigure the test db
    # connection in unit tests?
    if hasattr(db, 'cl_init'):
        db.cl_init(change_program='testsuite')

    print('database init', db, db._cursor)
    yield db
    print('database rollback', db, db._cursor)
    db.rollback()


@pytest.fixture
def constant_module(database):
    """ Patched `Cerebrum.Constants` module.

    This fixture patches the _CerebrumCode constants, so that they use the same
    database transaction as the `database` fixture.

    It also patches each _CerebrumCode subclass, so that the constant cache is
    cleared for each scope.

    """
    from Cerebrum import Constants
    # Patch the `sql` property to always return a known db-object
    Constants._CerebrumCode.sql = property(lambda *args: database)
    # Clear the constants cache of each _CerebrumCode class, to avoid caching
    # intvals that doesn't exist in the database.

    # issubclass fails on non-types, and PY2 has two meta types
    if six.PY2:
        meta_types = (type, types.ClassType)
    else:
        meta_types = (type,)

    for item in vars(Constants).values():
        if (isinstance(item, meta_types)
                and issubclass(item, Constants._CerebrumCode)):
            item._cache = dict()
    return Constants


@pytest.fixture
def const(database, constant_module):
    """ Cerebrum core constants. """
    return constant_module.Constants(database)


@pytest.fixture
def clconst(database, constant_module):
    """ Cerebrum core constants. """
    return constant_module.CLConstants(database)


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
