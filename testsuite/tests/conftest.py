# encoding: utf-8
"""
Global py-test config and fixtures.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

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
def database_cls(factory):
    # TODO: This isn't ideal. We shouldn't use Factory to get our db driver,
    # and *really* shouldn't use a bunch of CL implementations when we run our
    # tests.  How *should* we build our db driver and ocnfigure the test db
    # connection in unit tests?
    base = factory.get('Database')

    class _DbWrapper(base):

        def commit(self):
            print('db.commit() trapped, running db.rollback()')
            super(_DbWrapper, self).rollback()

        def rollback(self):
            print('db.rollback()')
            super(_DbWrapper, self).rollback()

        def close(self):
            print('db.close()')
            super(_DbWrapper, self).close()

    return _DbWrapper


@pytest.fixture
def database(database_cls):
    """`Cerebrum.database.Database` with automatic rollback."""
    db = database_cls()

    if hasattr(db, 'cl_init'):
        db.cl_init(change_program='testsuite')

    print('database init', db, db._cursor)
    yield db
    print('database rollback', db, db._cursor)
    db.rollback()


# A note on using constants in tests:
#
# Constants in CoreConstants or CommonConstants can generally be used without
# issues, as they always appear in Factory.get("Constants"), as well as our
# common constant test fixture (`const`).
#
# There *may* still be issues using these constants if a class in
# Factory.get("Constants") overrides a constant attribute from CoreConstants or
# CommonConstants.  This happens e.g. with system_manual in environments with
# ConstantsUniversityColleges.
#
# Also, the source system attribute "system_cached" often has special business
# logic, and is automatically populated on `write_db()` in some cases, and is
# best avoided in tests.
#
# If a test requires a constant, and no suitable constants exists in
# CoreConstants/CommonConstants, you'll probably have to create it.
# The `constant_creator` fixture can be used in these cases.


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
def constant_creator(constant_module):
    """
    A function that can create constants.

    Constants that are created with this fixture function will exist in the
    database *and* be present in the `const` fixture/fetchable with
    `const.get_constant()`.
    """
    attrs = []

    def create_constant(constant_type, value, *args, **kwargs):
        """
        Typical use:
        ::

            ID_FOO_STRVAL = "foo-id-type"

            @pytest.fixture
            def id_foo(constant_creator, constant_module):
                return constant_creator(
                    constant_module._EntityExternalIdCode,
                    ID_TYPE_FOO,
                    constant_module.CoreConstants.entity_person,
                )
        """
        description = kwargs.pop('description',
                                 "test constant " + six.text_type(value))
        kwargs['description'] = description
        code = constant_type(value, *args, **kwargs)
        code.insert()

        # Inject the code as an attribute of a class that exists both in
        # in the Factory.get("Constants") and `const` fixture mro
        #
        # This is needed for some of the ConstantsBase lookup methods (e.g.
        # `get_constant`)
        attr = 'test_code_' + format(id(code), 'x')
        setattr(constant_module.CoreConstants, attr, code)
        attrs.append(attr)
        return code

    yield create_constant

    for attr in attrs:
        delattr(constant_module.CoreConstants, attr)


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
