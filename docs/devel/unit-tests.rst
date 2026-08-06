======================
Unit tests in Cerebrum
======================


Test placement
===============
Tests are grouped in the following categories:

testsuite/tests/core
    Tests for core functionality, or modules that *should always work in any
    environment*.

testsuite/tests/modules
    Tests for optional functionality, typically for modules that requires
    optional database schemas.

testsuite/tests/\*
    Tests for optional functionality with external dependencies.  E.g.  ``gpg``,
    which needs a gnupg installation to work correctly.

Within each category, tests are mostly structured in a similar file hierarchy to
the code it tests.  In certain scenarios, one mode may be split into multiple
test modules (e.g. if a *lot* of fixtures are needed). See the existing file
layout in ``testsuite/tests/`` for examples.


Test fixtures
==============
*Never* depend on specific configuration (e.g. ``cereconf``), or pre-existing
database data.

Exceptions — certain settings that *must* exist in any working environment:

``cereconf.INITIAL_ACCOUNTNAME`` and ``cereconf.INITIAL_GROUPNAME``
    You can assume that these entities exists.  Use the common fixtures
    ``initial_account`` and ``initial_group`` to get these entities.


``Cerebrum.Constants.Constants`` and ``Cerebrum.Constants.CLConstants``
    These constants should exist, and can be fetched using the common ``const``
    and ``clconst`` fixtures.

    Other constants must be manually inserted/created/mixed in if used by tests.


Database settings
    The test database should be configured correctly in ``cereconf``.  Use the
    ``database`` fixture to get a database connection.  Note that ``commit`` is
    overloaded in this fixture - any ``commit`` will actually rollback the
    current transaction.

    This may conflict with some legacy functionality, but that legacy
    functionality should probably be re-written.


Factory classes
    ``Factory.get(<name>)`` should generally produce working classes, but you
    should never *depend* on specific mix-ins in any unit test.


``cereconf``
-------------
The cereconf config module is available for import, but no test should
depend on any pre-existing config here.

If you need a specific cereconf-value to be set in a unit test, use the
``cereconf`` fixture to patch the current cereconf module:

E.g.:
::

    @pytest.fixture(autouse=True)
    def _patch_cereconf(cereconf):
        cereconf.FOO = "bar"

Note that this won't work for (legacy) code that *copies* cereconf values
(e.g. by doing ``from cereconf import VALUE``) rather than using a
reference.


Logging
--------
Log records can be tested by using the default pytest ``caplog`` fixtures.

The ``Cerebrum.testutils.log_utils.StrictNullHandler`` can be used to catch bugs
in log formatting.  This handler throws an exception if any log messages are
unable to be formatted, causing a test failure:
::

    from Cerebrum import module_to_test

    @pytest.fixture(scope="module", autouse=True)
    def _patch_module_logger():
        """ catch badly formatted log records in module_to_test. """
        module_to_test.logger.addHandler(StrictNullHandler())
        module_to_test.logger.setLevel(-100)


Constants
---------
A lot of code depends on optional constants in the database, but our tests can't
depend on specific ``cereconf.CLASS_CONSTANTS`` to provide the correct mixins.

The ``constant_creator`` fixture can be used to create *new* constants, and
insert them into the base ``Cerebrum.Constants.Constants`` class.  This
makes them available to code that use ``Factory.get("Constants")`` to look
up constant values.
