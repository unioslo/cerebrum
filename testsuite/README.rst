==============================
Automated tests for Cerebrum
==============================

A short introduction to unit testing in Cerebrum.

Dependencies
============

Cerebrum uses the *pytest* framework for unit testing.  Please read up on the
pytest documentation before running or writing tests.

- ``pytest`` (required)
- ``pytest-cov`` (recommended)


File structure
===============
TL;DR: All unit tests are in ``testsuite/tests/``, everything else in
``testsuite/`` is related to setting up test environments.

testsuite/tests
---------------
Contains unit tests and test setup.  Unit tests are separated into three
categories, each one with its own directory:

``core/``
    Unit tests for modules that should work in *any* Cerebrum-environment are
    placed in ``testsuite/tests/core/``.  These tests should run in any
    environment with the core cerebrum database schema, and should *not* depend
    on any special pre-existing ``cereconf`` settings.

``modules/``
    Modules that may only work in some environments (e.g. requires optional
    database schemas) are placed in ``testsuite/tests/modules/``.  Note that
    these tests should still not depend on any pre-existing cereconf settings
    (other than the basics, like database connection details, and other core
    settings).

``*/``
    All other test modules should be placed in their own directory.  This
    typically applies to test modules that:

    - Requires special setup (e.g. optional dependencies, pre-existing config
      modules, or any other test setup that cannot be automated or mocked)
    - Requires external systems (other than a database)
    - Takes a really long time to run

    One example is ``testsuite/tests/gpg/``, which requires optional
    dependencies and test fixtures.  Notably, it also needs a gnupghome
    directory which is created using a ``pytest.fixture``.

testsuite/scripts
------------------
Helper scripts for setting up a test envionment.

testsuite/ansible
-----------------
Ansible playbooks for setting up test runners.  Most of these are obsolete.

testsuite/docker
-----------------
Various scripts and helper files for setting up containers for running unit
tests.  Most of these are obsolete.


Running tests
==============
If you already have a working dev environment, you probably have everything you
need to run _most_ tests.  Note that all tests won't work in all given test
environments, as some of the tests may depend on optional Cerebrum
functionality that your dev environment may be missing.

To run e.g. all *core* tests:
::

    python -m pytest tests/core/


When developing and running tests for the module you're working on, you would
typically use the ``-v`` option, to list individual tests as they run:
::

    python -m pytest -v testsuite/tests/modules/test_foo.py

When developing unit tests, you may want to check the coverage of the module
you're testing, and identify untested lines.  If you're writing tests for a
module ``Cerebrum.modules.foo``, the following example will provide a percentage
summary and list untested lines:
::

    python -m pytest -v \
        --cov=Cerebrum.modules.foo --cov-report=term-missing \
        testsuite/tests/modules/test_foo.py


Writing tests
==============
To write a test module, simply create an appropriate directory and test module.
If you write e.g. a new module ``Cerebrum.utils.foo``, you would also
create the test module ``tests/core/utils/test_foo.py``.  If you need to split
your tests for a given module across multiple test modules:

- Create multiple modules (e.g. ``test_foo_something.py`` and
  ``test_foo_something_else.py``)

- Create a subdirectory for your tests (``foo/test_foo_a.py``,
  ``foo/test_foo_b.py``).  This can also be useful if you want a ``conftest.py``
  that only applies to your tests.


test fixtures and setup
------------------------
Use ``pytest.fixture`` for all test setup and teardown, monkey patching, etc...

Simple fixtures and fixtures that are only used in a single test module should
be placed in the test module iteself.

To share test fixtures between modules, create or update a ``conftest.py``
module in the same subdirectory as your test module.

See the *pytest* documentation for more info on fixtures and ``conftest``.

The top-level directory contains fixtures for setting up the database
connection/transaction, constants, etc.  Please read through this conftest
module before writing any tests.

Some important, common fixtures:

``database``
    A database connection/transaction.  *Always* use this fixture for any tests
    or fixtures that requires a database connection.  The ``database`` fixture
    automatically rolls back any changes after each unit test.

``const`` and ``clconst``
    A ``Cerebrum.Constants.ConstantsBase`` container.  *Always* use this for any
    tests and fixtures that requires constants.

    Note that this only contains the constants from ``CoreConstants`` +
    ``CommonConstants``.  If you need any other constants, you
    should use the ``constant_creator`` fixture to create temporary constants
    for use in your tests.

    If in doubt, look at tests for similar modules to yours.

``cereconf``
    A ``cereconf`` module.  Note that this ``cereconf`` module contains all the
    settings from your actual test environment ``cereconf`` module.  Your tests
    should not *depend* on any specific values here though.

    If you need a certain value to exist in the ``cereconf``, you should patch
    it in a fixture:
    ::

        @pytest.fixture(autouse=True)
        def _patch_cereconf(cereconf):
            cereconf.FOO = "bar"

    Also note that some modules may make a copy of a given cereconf setting on
    import (e.g. ``from cereconf import FOO``).  If this happens, you should
    probably rewrite the module to always fetch the current ``cereconf`` value
    (to make monkey patching the value possible), or you'll need to monkey patch
    the copied value as well.


Test utils
----------
Re-usable test utils are placed in ``Cerebrum.testutils``.  These are some of
the helper modules:

``Cerebrum.testutils.file_utils``
    Helpers for creating temporary directories and files.

``Cerebrum.testutils.datasource`` + ``Cerebrum.testutils.dbtools``
    Helpers for creating database fixtures.  E.g. create ``Person``, ``Group``,
    or ``Account`` objects for use in tests.

``Cerebrum.testutils.log_utils``
    Helpers for testing logging and log messages.

    If the module you're writing unit tests for are logging, you should patch
    the test module and add a ``StrictNullHandler`` for the relevant loggers.

    Typical use:
    ::

        import foo  # the module we're testing

        @pytest.fixture(scope="module")
        def logger():
            """ A logger object. """
            return logging.getLogger(__name__)


        @pytest.fixture(scope="module", autouse=True)
        def _patch_logging(logger):
            """ catch badly formatted log records in foo module log messages. """
            logger.addHandler(StrictNullHandler())
            logger.setLevel(-100)
            foo.logger = logger

    Your test will then catch log message formatting errors like:
    ::

        foo.logger.info("Values a=%d, b=%s", None, "foo")
        foo.logger.info("Values a=%d, b=%s", 3)
        foo.logger.info("Values a=%d, b=%s", 3, "foo", "bar")

    ... which would *normally* just cause an error to be logged.


Best practice
-------------
When writing tests, there are a couple of things to keep in mind:

1. Write *unit* tests.  Your tests should not depend on outside factors (e.g.
   certain cereconf values, pre-existing database values that may or may not
   exist, etc...)

2. Some tests *do* require e.g. an account or some other pre-existing data.  In
   these cases, you should write *fixtures* to set up these tests.

3. Keep things simple.  A unit test should only test *one* thing.

4. Name your tests appropriately.  It should be fairly easy to know what your
   test checks in a summary of tests.

5. Write fast tests.  If a given test is slow, consider making it optional.


Pitfalls
--------
Complicated setup
    If your test fixture or tests get really complicated, then maybe the code
    you're testing is too complicated.  It may be better to refactor the code
    before implementing unit tests.


Test fatigue
    Testing *every* possible test input, or writing a million tests to achieve
    100% coverage can result in *test fatigue*.  Always consider that someone
    may have to *change* the behaviour of the module you're testing, or may have
    to add to the test module.


Caveats
=======
The Cerebrum unit tests are mostly meant for manual testing, and not suitable
for automatic testing.  This is mostly due to some Cerebrum implementation
details.

This can be fixed, but needs a *lot* of refactoring.  Some of the most pressing
issues:

1. Use of global state (e.g. a separate database connection in constants).

2. Optional modules and features that are injected in code code.  A *lot* of
   code depends on classes constructed by ``Factory.get``

3. Optional database schemas.  A lot of modules and code depend on pre-existing
   database setup.

Over time, some of these issues will (hopefully) be re-factored away.
