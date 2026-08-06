=================
Cerebrum.logutils
=================

.. contents::

``Cerebrum.logutils`` is a set of modules for *bootstapping* the standard
logging module for Python.  This document is a description of the
``Cerebrum.logutils`` module configuration, module internals, and how it is used
in Cerebrum.


Configuration
=============
There are two different types of configuration for the ``Cerebrum.logutils``
module:

- `logging environment`_ config (logenv), with settings for ``Cerebrum.logutils``
- `logger preset`_, with settings for the loggers and handlers used by a
  given script


Logging environment
-------------------
The logging enviromnent config is a configuration file with name ``logenv``,
that resides in the Cerebrum configuration directory
(``<prefix>/etc/cerebrum/config`` by default).

To see the current settings, run:
::

    python -m Cerebrum.logutils.config

To see the documentation for this configuration, run:
::

    python -c 'import Cerebrum.logutils.config as c; print(c.LoggingEnvironment.documentation())'


Settings
~~~~~~~~~

``logging.confdir`` (string, directory)
    Location of `logger preset`_ configurations, i.e. a folder with standard
    logging configuration files.

``logging.logdir`` (string, directory)
    Root directory of logs. This will be the value that replaces ``${root}`` in
    the ``filename`` argument of  ``Cerebrum.logutils.handlers`` loghandlers.

``logging.common_config`` (string, preset/basename)
    A `logger preset`_ name that contains *common* logging configuration. When
    the logging hierarchy is configured during `bootstrap`_, this config file
    will be loaded and applied *before* the named preset.

        **NOTE**: If no file exists in ``logging.confdir`` with the given common
        config name, this file will be silently skipped.

``logging.merge`` (boolean)
    If the common config should be *merged* with the ``logging.common_config``
    before being applied.  Setting this to ``True`` will cause the config
    loading to behave differently:

    1. Any handlers applied to the *root logger* in ``logging.common_config``
       will persist after loading the *named preset*.
    2. Names of handlers, filters, etc. defined in ``logging.common_config`` can
       be used in the *named preset*.
    3. If the *named preset* specifies to disable existing loggers, this will
       not disable anything defined in the ``logging.common_config``.

        **NOTE**: It is not possible to *merge* configuration files if any of
        the configurations use an *ini* style configuration
        (``logging.config.fileConfig``).

``logging.require_config`` (boolean)
    Causes scripts to fail if the *named preset* does not exist in
    ``logging.confdir``.  Setting this to ``True`` prevents scripts from running
    without a proper logging configuration.

    If set to false, and no appropriate logging presets are found, the logging
    hierarchy will be configured with ``logging.basicSetup()`` - i.e. log to
    stderr.

``exceptions.enable`` (boolean)
    Enable logging of `exceptions`_.

``exceptions.level`` (string, log level)
    The log level to use for `exceptions`_.

``warnings.enable`` (boolean)
    Enable logging of `warnings`_.

``warnings.level`` (string, log level)
    The log level to use for `warnings`_.

``warnings.filters`` (list, filter strings)
    A list of extra warning filters to apply.

``sentry.enable`` (boolean)
    Enable `sentry`_ integration.

``sentry.dns`` (string, url)
    A `sentry`_ DSN/URL to use for errors.

    E.g.: ``https://<token>@example.org/<project>"``

``sentry.environment`` (string)
    A environment value for Sentry errors/issues.

    Defaults to ``cereconf.ENVIRONMENT`` if not given.


Logger preset
-------------
Logger presets are regular configuration files for the python `logging`_ module,
and configures the logger hierarchy (loggers, handlers, filters, formatters).

The presets should reside in the directory given by the `logging environment`_
config (``logging.confdir``, ``<preset>/var/log/cerebrum`` by default).

Scripts usually select a *default* named  preset (usually ``"crontab"``) when
setting up the logging hierarchy.  This default preset can be overloaded with
command line `arguments`_.


Arguments
=========
Cerebrum-scripts that use ``logutils`` will also automatically support a few
extra command line arguments that overrides the logging defaults:

- ``--logger-name=<preset>``: use a different preset name for logging
- ``--logger-level=<level>``: use a different logger level for the root logger
- ``--logger-exc|--logger-no-exc``: turn on/off the `exceptions`_ logging
- ``--logger-warn|--logger-no-warn``: turn on/off the `warnings`_ logging
- ``--logger-sentry|--logger-no-sentry``: turn on/off the `sentry`_ integration

Scripts that use ``argparse`` should use a preset argument group, and pass on
the arguments to the logging `bootstrap`_:
::

    import argparse
    from Cerebrum.logutils import autoconf
    from Cerebrum.logutils.options import install_subparser

    parser = argparse.ArgumentParser()
    # ... add custom arguments

    # Add logging argument group
    install_subparser(parser)

    # Parse arguments
    args = parser.parse_args()

    # Run logging bootstrap
    autoconf('cronjob', args)


If ``autoconf`` is called *without* an argparse namespace object (e.g.
``autoconf('cronjob')``), the `bootstrap`_ runs in *legacy* mode. The command
line arguments are then fetched directly from ``sys.argv``, applied to the
bootstrap configuration, and then removed from ``sys.argv``.


.. note::
    The --logger-sentry argument will only be able to turn *on* the sentry
    integration if the logging environment `configuration`_ contains a valid
    ``sentry.dsn`` setting.

    This pair of arguments are mainly used to turn *off* a default-on
    integration.


Exceptions
==========
In scripts that use ``logutils``, a custom exception handler can optionally be
set up, that also sends the error message and stack trace of unhandled
exceptions to a logger. This behaviour can be configured in the logging
environment `configuration`_, and overridden by command line `arguments`_.

    **NOTE**: Any exception raised before or during bootstrap, will be handled
    by the default exception handler, i.e. get printed to ``sys.stderr``.


Warnings
========
In scripts that use ``logutils``, a custom warnings handler can optionally be
set up, that logs warning messages with a logger.  This behaviour can be
configured in the logging environment `configuration`_, and overridden by
command line `arguments`_.

    **NOTE**: Any warning issued before bootstrap will be handled by the default
    warnings handler, i.e. get printed to ``sys.stderr``.

Filtering
---------
Warnings can be filtered away in Python, and certain filters are already in
place by default. This behaviour is described well in the Python-documentation
of the `warnings-module`_.

The logging `bootstrap`_ clears all the default warning filters, and re-applies
filters from:

1. The ``PYTHONWARNINGS`` environment variable
2. The ``-W`` option to ``python``
3. Filters defined in the warnings section of the logging environment
   `configuration`_

    **NOTE**: Python ignores incorrecly formatted filters by default. The
    ``logutils`` module does not accept invalid filter-syntac, and throws an
    exception if any invalid filter strings are used.


Sentry
======
Cerebrum supports integration with Sentry, which will send error log messages
to a given project in the Sentry service provided using the ``dsn`` setting.

If enabled, the log configuration will will set up a Sentry integration using
``sentry_sdk``.


Bootstrap
=========
The logging bootstrap sets up the logging environment, by doing the following:

#. Install custom log levels and logger class in the ``logging`` module
#. Parse command line `arguments`_ (legacy-mode), or read command line arguments
   from a pre-parsed ``argparse.Namespace`` object.
#. Read the logging environment `configuration`_
#. (legacy-mode only) read ``cereconf`` settings (``LOGGER_ROOT_DIR``,
   ``PYTHONWARNINGS``)
#. Use the configured logger preset (``logger-name``) to find a logger
   `configuration`_ and configure the logger hierarchy.
#. Configure the `exceptions`_ hook, if enabled
#. Configure the `warnings`_ handler, if enabled


This bootstrap can be called multiple times, but will *only run once*, and is
initiated by calling ``Cerebrum.logutils:autoconf()``:

::

    from Cerebrum.logutils import autoconf
    autoconf('cronjob', namespace=None)


The first argument is the default `logger preset`_ for this script. This preset
is used if no ``--logger-name`` `arguments`_ are given.

The second argument is an ``argparse.Namespace`` object from parsing command
line `arguments`_, that may or may not contain any logging arguments.

If no ``namespace``-object is given to ``autoconf``, then it will execute in
*legacy mode*!

If ``Cerebrum.Utils:Factory.get_logger`` or ``Cerebrum.logutils:getLogger`` is
called before bootstrap, the ``autoconf`` will be called, and will run in legacy
mode.  This ensures that pre-existing Cerebrum-scripts that are not altered to
use this module will continue to work as before.


Submodules
==========
The ``Cerebrum.logutils`` consists of:

``Cerebrum.logutils``
    Bootstrapping of the logging environment. See the `bootstrap`_ section for
    a description of this procedure.

``Cerebrum.logutils.config``.
    Logutils-configuration, configures the logging environment and bootstrap.
    See the `configuration`_ section for more details.

``Cerebrum.logutils.filters``
    Custom logging filters that can be applied to loggers and log handlers.

``Cerebrum.logutils.formatters``
    Custom logging formatters that can be used by log handlers.

``Cerebrum.logutils.handlers``
    Custom file log handlers. These log handlers works much like the regular
    python log handlers, but with a few modifications:

    - Filename arguments can be *template* strings
    - Directories are created if missing
    - Log file creation is delayed by default
    - A custom re-encoding file stream is used, for logging both latin1 and
      utf-8 bytestrings, as well as unicode-strings.
    - The CerebrumRotatingHandler uses threading locks, to prevent race conditions
      when performing the log rotation.
    - The CerebrumTimedRotatingHandler uses threading locks like CerebrumRotatingHandler,
      but instead of rotating based on file size, it rotates based on time.

``Cerebrum.logutils.logexc``
    Utilities for setting up logging of unhandled `exceptions`_.

``Cerebrum.logutils.logwarn``
    Utilities for setting up logging of `warnings`_.

``Cerebrum.logutils.options``
    Utilities for parsing command line `arguments`_.

``Cerebrum.logutils.stream``
    Custom streams/file-like objects for writing log files.

Handlers
---------
The ``Cerebrum.logutils.handlers`` consists of:

``OneRunHandler``
    A file handler that logs one job run into exactly one log file.

``CerebrumRotatingHandler``
    This handler rotates the logs much like handlers.RotatingFileHandler,
    except that the file opening is delayed, and rotation requires threading
    locks.

    Rollover occurs when the current file is nearly maxBytes long.

    Arguments:

      - maxBytes: Maximum file size before rollover
      - backupCount: How many backups to keep
      - filename: Path to file. Accepts keywords ${root}, ${date} and ${script}
      - permissions: Which permissions to set for file i.e 0640
      - encoding: Which encoding to use when writing to file, i.e utf-8
      - level: Which logger level this logger is used for, i.e ERROR, WARNING, etc. Can be NOTSET to log everything not logged by something else.

``CerebrumTimedRotatingHandler``
    Pretty much a copy of ``logging.handlers.TimedRotatingHandler``. Rotates based on time.

    Arguments:

      - when: One of 'S', 'M', 'H', 'D', 'midnight', 'W{0-6}' (0 -Monday). Each results in their own formats for backup file names.
      - interval: The interval at which to rollover
      - backupCount: How many backups to keep
      - filename: Path to file. Accepts keywords ${root}, ${date} and ${script}
      - permissions: Which permissions to set for file i.e 0640
      - encoding: Which encoding to use when writing to file, i.e utf-8
      - level: Which logger level this logger is used for, i.e ERROR, WARNING, etc. Can be NOTSET to log everything not logged by something else.

    Examples:

      - when: 'S', interval: 5, backupCount: 2 - rolling over every 5 seconds, keeping 2 backups, resulting in maximum 14s logged.
      - when: 'D', interval: 2, backupCount: 2 - rolling over every 2 days at midnight, keeping 2 backups, resulting in maximum 2d59m59s logged.
      - when: 'H', interval: 6, backupCount: 5 - rolling over every 6 hours, keeping 5 backups, resulting in maximum 1d11h59m59s logged.

.. _warnings-module: https://docs.python.org/2/library/warnings.html
.. _logging: https://docs.python.org/2/library/logging.html#logging.captureWarnings
.. _logging.config: https://docs.python.org/2/library/logging.config.html
.. _captureWarnings: https://docs.python.org/2/library/logging.html#logging.captureWarnings
