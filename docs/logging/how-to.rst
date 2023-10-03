=======================
How to log in Cerebrum
=======================

Write short and clear log messages, and use string interpolation for variable
content.

Some logging guidelines and tips:

* Use ``Cerebrum.logutils`` to configure all logging.  See the `example`_
  further down.

* Consider the different `log levels`_ before adding a new log record.

* Use string interpolation: ``info("foo=%s", foo)``, **not**
  ``info("foo=%s" % (foo,))```.

* Only log serializable arguments, and use *repr* if an argument could be
  unserializable.  Generally prefer ``info("foo=%s", repr(foo))`` over
  ``info("foo=%r", foo)``.

* Add context when logging values, e.g.: ``skipping account_name=%s,
  person_id=%d``, and **not** just ``skipping %s, %d``

* Follow GDPR_ guidelines:

  - Don't log personal information, unless really, really necessary.

  - When logging details about persons, prefer to log internal ids like
    ``entity_id`` over *personal identifiers*.

  - This also applies to the *DEBUG* level.

  - If personal information *really* needs to be logged for debugging, use a
    separate logger that is *disabled* by default.

* Log exception tracebacks if caught.  Tracebacks can be omitted for really,
  really known and expected exceptions, otherwise log a message with the
  appropriate level (usually *ERROR*) and with ``exc_info=True``.


Log levels
===========
In normal operation, scripts should log at level *INFO*.  *DEBUG* is
reserved for manual runs when more information is needed.

**CRITICAL**
    Only for emergencies where sysadmins need to take action immediately.  This
    is typically when a batch script or daemon process crashes.

**ERROR**
    Whenever something that *should* succeed unexpectedly fails.  Everything
    logged at this level or higher should be followed up by a person.

    Examples:

    - Tried to communicate with an external system, but the system is unreachable.

    - Tried to communicate with a system, but the system returns an error

    - Tried to process a request, but an exception was raised.

**WARNING**
    Used for somewhat expected errors, and situations that should be *noticed*.
    A warning indicates that something is odd or wrong, but it may not require
    follow-up.

    Examples:

    - A user was omitted from batch import/export because of bad data.

**INFO**
    Details that document state changes.

    Examples:

    - Actual changes to internal/external systems.
    - Process startup and shutdown (e.g. batch script start/stop).
    - Milestones in batch processing

**DEBUG**
    Useful details for debugging, but not for daily operations, a.k.a. *the
    rest*.  Still, no sensitive data, please.

    Logs should be readable if this information is omitted.


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
    default_preset = 'tee' if args.commit else 'console'
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("start %s", parser.prog)


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
    debug_log.propagate = False
    debug_log.addHandler(logging.NullHandler())


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


.. _GDPR: <https://www.regjeringen.no/no/tema/lov-og-rett/innsikt/ny-personopplysningslov/>
