==============
Writing tests
==============

When writing unit tests for Cerebrum, please follow the general guidelines from
:doc:`writing-code` and :doc:`code-style`.


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
the code it tests.  In certain scenarios, one module may be split into multiple
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


cereconf
---------
While a :doc:`/config/cereconf` config module must be available for import when
running tests, no test should depend on any pre-existing config here.

The ``cereconf`` module should just provide database settings, and general
settings *not* directly used by the code being tested.  Tests should generally
pass regardless of any settings in the current cereconf module.

If you need a specific cereconf-value to be set for a unit test, use the
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

The ``const`` and ``clconst`` fixtures should provide you with constants defined
in ``Cerebrum.Constants.Constants`` and ``Cerebrum.Constants.CLConstants``.
These constants should always exist in a Cerebrum database.

Other constants must be manually inserted/created/mixed in if required by
a given unit test.

The ``constant_creator`` fixture can be used to create *new* constants, and
insert them into the base ``Cerebrum.Constants.Constants`` class.  This
makes them available both to code that use ``Factory.get("Constants")`` and the
``const`` fixture to look up constant values.
