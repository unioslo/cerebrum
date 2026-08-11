===================
How to use logging
===================

.. contents::


Overview
=========
This document describes coding conventions, tips and tricks, and some useful
code patterns to use in Cerebrum.


Configuring logging in Cerebrum
--------------------------------
Cerebrum uses *two* distinct log configs.

The first configures the *logging environment*, and specifies some default
locations for log files, locations for *logger presets*, general behaviour, etc...

The second config is the *logger preset* (specified as ``--logger-name`` in most
scripts).  This preset configures the logger hierarchy, with loggers, handlers,
formatters, etc...

See :doc:`logutils` for more details on the logging framework ands its
configuration files.


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

- Debug loggers (e.g. for sensitive information).  These loggers should
  typically be omitted from the logger hierarchy by default:
  ::

      debug_log = logger.getChild("debug")
      debug_log.addHandler(logging.NullHandler)
      debug_log.propagate = False

  See `Logging sensitive debug data`_ for more details.

In summary - if something other than a module logger is needed, create a
child of a module logger that *doesn't* collide with another module name.


Writing code
=============
Write short and clear log messages, and use string interpolation for variable
content.

When creating log records:

- (almost) always use the module level logger

- follow GDPR_ guidelines:

  - avoid logging personal data or sensitive information

  - when logging details about a person, prefer to log internal ids like
    ``entity_id``

  - this also applies to the *DEBUG* level.

  - if personal information *really* needs to be logged for debugging, use a
    separate logger that is *disabled* by default.

- Use ``Cerebrum.logutils`` to configure all logging.  See the `example`_
  further down.

- Consider the different `log levels`_ before adding a new log record.

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
In normal operation, scripts should log at level *INFO*.  *DEBUG* is
reserved for manual runs when more information is needed.

.. _log levels:

**CRITICAL**
    Serious problems, should rarely be used.

    Only for emergencies where sysadmins need to take action immediately.

    E.g.: a daemon terminates unexpectedly, database unavailable.

**ERROR**
    Unhandled errors, anything that requires manual interaction.

    Whenever something that *should* succeed unexpectedly fails.  Everything
    logged at this level or higher should be followed up by a person.

    Examples:

    - Tried to communicate with an external system, but the system is unreachable.
    - Tried to communicate with a system, but the system returns an error
    - Tried to process a request, but an exception was raised and not handled
    - Tried to read a required file, but the file is missing

**WARNING**
    Used for somewhat expected errors, and situations that should be *noticed*.

    A warning indicates that something is odd or wrong, but it may not require
    follow-up.

    Examples:

    - A user was omitted from batch import/export because of bad data.
    - Most examples from *ERROR* that are expected, and handled well

**INFO**
    Important messages, and details that document state changes.

    Examples:

    - Important events, e.g.: startup, shutdown, new request, new response
    - Actual changes to internal/external systems, e.g.: database changes,
      filesystem changes, external command invocations and results
    - Milestones in batch processing

**DEBUG**
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


Example
========
The following script demonstrates how to set up logging in a typical Cerebrum
script:

Example:
::

    import argparse
    import logging

    import Cerebrum.logutils
    import Cerebrum.logutils.options

    logger = logging.getLogger(__name__)


    def main(inargs=None):
        parser = argparse.ArgumentParser("...")
        # add script arguments here ...
        Cerebrum.logutils.options.install_subparser(parser)

        args = parser.parse_args(inargs)
        Cerebrum.logutils.autoconf("cronjob", args)

        logger.info("start %s", parser.prog)
        logger.debug("args: %s", repr(args))

        # do some stuff here ...

        logger.info("done %s", parser.prog)


    if __name__ == '__main__':
        main()


Default logger presets
=======================
Any script with logging will refer to a *default logger preset* that will be
used if no ``--logger-name`` argument is given on the command line.

When writing scripts, you can expect a Cerebrum environment to have the
following presets:

console
    Typically uses a log handler that logs to stdout or stderr.  No other
    handlers (side effects).

    Use this as a default in *interactive* read-only scripts - i.e. scripts that
    a human will run manually to fetch information from Cerebrum or other,
    related systems.

cronjob
    Log handlers that logs to file.  This preset typically logs to a path based
    on the script name, and rotates logs based on size.  May also have handlers
    for Sentry, ELK, or similar distributed systems.

    This is the most used preset, and is typically for scripts that runs
    unsupervised in the background through *job runner* or some other scheduler.

daemons
    Log handlers that logs to file.  This preset typically logs to a path based
    on the script name, but unlike "cronjob" this handler should rotate logs
    based on time (typically daily).  May also have handlers for Sentry, ELK, or
    similar distributed systems.

    This is a suitable preset for daemons in Cerebrum, e.g. bofhd,
    task-consumer, event-publisher.

tee
    Typically the handlers from *console* + handlers from *cronjob*.

    Use this as a default in *interactive* scripts that alters the state of
    Cerebrum or other systems - i.e. scripts that a human will run manually in
    order to change something in the database.

daily
    Similar to ``cronjob``, but rotates logs daily, and includes the date in the
    log filename.

    This is a good alternative to cronjob, but typically requires cleanup
    using :doc:`/maintenance/file-cleaner`.  This is very useful for scripts
    that either:

    - Logs a lot - we can add compression to save space, and prevents us from
      rotating away logs too quickly.

    - Logs very little - when combined with cleanup, this prevents us from
      keeping logs around too long.


Convenient patterns
====================

Conditional logger preset
--------------------------
For interactive (manual run) scripts with a commit/dryrun options, let the
commit/dryrun flag control the default preset:

::

    parser = argparse.ArgumentParser("...")
    Cerebrum.utils.argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf_interactive(args)
    # This is the same as setting:
    #   `logutils.autoconf('tee' if args.commit else 'console', args)`

    logger.info("start %s", parser.prog)
    ...


Logging sensitive debug data
-----------------------------
Seeing actual values can sometimes be crucial when debugging.  However, if these
values contains personal information, they should not be logged by default.

It's possible to make logging *conditional* by using a logger that is disabled
by default.  Example:

::

    # default, module level logger
    logger = logging.getLogger(__name__)

    # additional disabled debug log
    debug_log = logger.getChild("debug")
    debug_log.addHandler(logging.NullHandler())
    debug_log.propagate = False


    def enable_debug_log():
        # note: may need to add threading locks here
        debug_log.propagate = True


    def example_func(data):
        internal_id = data.get('id')
        logger.debug("processing id=%s", repr(external_id))

        sensitive_value = data.get('secret')
        debug_log.debug("got secret=%s for id=%s",
                        repr(sensitive_value),
                        repr(internal_id))


Anything logged using the ``debug_log`` is discarded by default, unless
configuration says otherwise.

- Call ``enable_debug_log`` to make records logged using ``debug_log`` propagate
  to the regular ``logger``.  Log records to these loggers should now be handled
  in the same way (unless the logger preset/log config explicitly says
  otherwise).

- A custom log config could be used to change the behaviour of the ``debug_log``
  (e.g. log these messages to a separate log file).


.. _gdpr: https://www.regjeringen.no/no/tema/lov-og-rett/innsikt/ny-personopplysningslov/
