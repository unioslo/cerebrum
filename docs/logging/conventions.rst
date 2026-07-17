===================================
Conventions for logging in Cerebrum
===================================

.. contents::

.. section-numbering::


Overview
=========
Most loggers will use the standard Python logger hierarchy, with handlers *only*
for the root logger.

Configuring logging in Cerebrum
--------------------------------
Cerebrum uses *two* distinct log configs.

The first configures the *logging environment*, and specifies some default
locations for log files, locations for *logger presets*, general behaviour, etc...

The second config is the *logger preset* (specified as ``--logger-name`` in most
scripts).  This preset configures the logger hierarchy, with loggers, handlers,
formatters, etc...

See `Cererbum.logutils <./logutils.html>`_ for details on how to configure.

Loggers and logging hierarchy
------------------------------
We generally use *module loggers*, i.e. globally defined loggers, named from
the modules they are defined in.  This generates a logger hierarchy that mirrors
our code, and loggers are adressable by their module names when configuring them
from our *logger presets*.

Exceptions to this rule:

- The common legacy logger returned by ``Factory.get_logger()`` — this logger
  should only be used in legacy code.

- Legacy code that requires a logger object — in these cases it's common to
  create a new child-logger from the current module: e.g.:
  ::

      def read_edu_units(filename):
          getter = EduDataGetter(filename, logger.getChild("read_edu_units"))
          ...

- Separate debug loggers (e.g. for sensitive information).  These are separate
  logger objects that aren't included in the logger hierarchy by default:
  ::

      debug_log = logger.getChild("debug")
      debug_log.addHandler(logging.NullHandler)
      debug_log.propagate = False

In summary - if something other than a module logger is needed, create a
child of a module logger that *doesn't* collide with another module logger.


Writing code
=============
When creating log records:

- (almost) always use the module level logger

- avoid logging personal data or sensitive information - follow GDPR_ guidelines.

- include all relevant data in the log message - log records should not depend
  on *context* (i.e. other log records):

  - **don't**: ``logger.debug("processing item=%s", item_id);
    logger.warning("invalid foo: %s", repr(foo))`` (second log record depends on
    first for context)

  - **do**: ``logger.debug("processing item=%s", item_id);
    logger.warning("invalid foo in item=%s: %s", item_id, repr(foo))`` (second
    log record contains all neccessary context).

- let the logger deal with formatting

  - **don't**: ``logger.info("Foo: %s" % (value,))``
  - **do**: ``logger.info("Foo: %s", value)``

- only log serializable values:

  - **don't**: ``logger.info("Foo: %r", some_complex_object)``
  - **do**: ``logger.info("Foo: %s", repr(some_complex_object))``

- use ``exc_info`` to log tracebacks:

  - **don't**: ``logger.exception("Unhandled error in request id=%s",
    request_id)``

  - **do**: ``logger.error("Unhandled error in request id=%s", request_id,
    exc_info=True)`` (explicit log level)

  - only log tracebacks for errors that would otherwise be lost/hidden.  E.g.
    for servers where the request ends up as a HTTP 500 response.  If an
    exception is re-raised, a traceback should normally *not* be logged.


Choosing a log level
---------------------
``DEBUG``
    Debug information, should not normally be handled or included in logs.  Logs
    should still make sense without this information.

    Should provide operators with useful info, e.g. (non-personal) identifiers
    for debugging.  When reading a debug log, the reader should be able to
    follow the program execution, and various decisions taken to produce the
    *changes* that are logged with level ``INFO``.

    Examples:

    - ``logger.debug("Found %d events to process", len(events))``
    - ``logger.debug("Ignoring event.id=%d - some criteria not fulfulled",
      event.id)``
    - ``logger.debug("Acting on event.id=%d", event.id)``

    Take care not to log *too much*.  Unneccessary log records makes a log
    harder to read and follow.

``INFO``
    - Important events, e.g.: startup, shutdown, new request, new response
    - All changes (i.e. database update, filesystem changes, external
      commands, external communication, ...)

``WARNING``
    Potential issues.  Something that shouldn't happen.  Errors that are
    handled, but should still be noted.

``ERROR``
    Unhandled errors, anything that requires manual interaction.  Examples:

    - Required file missing
    - Invalid value in input

``CRITICAL``
    Serious problems, should rarely be used.

    E.g.: a daemon terminates unexpectedly, database unavailable.


Legacy log levels
------------------
A custom Cerebrum logger exists in Cerebrum, with additional ``DEBUG`` log
levels (``DEBUG1``, ``DEBUG2``, etc..).  This is a legacy feature, and should be
avoided in *all new code*.


Ignoring log messages
----------------------
Sometimes, appropriate log records from a given logger (e.g. some module
logger), is inappropriate in the context where it is used (e.g. a script).

Example: ``Cerebrum.modules.statsd`` communicates with an external system, where
it also mutates data - this should be logged at level ``INFO``.  The script
``create_foo.py``, creates a *foo* object in the database, and logs this at
level ``INFO``, then counts a stat value using statsd.  In this case, it's not
interesting to know in our logs for ``create_foo.py`` that the stats module does
what it does - it is simply not all that important.

In these cases, the appropriate solution is to *ignore* messages to the given
logger in the log configuration.

.. _gdpr: https://www.regjeringen.no/no/tema/lov-og-rett/innsikt/ny-personopplysningslov/
