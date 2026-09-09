# -*- coding: utf-8 -*-
#
# Copyright 2017-2026 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Logging setup.

This module is the entry-point for the Cerebrum logging framework.  See
:mod:`logging` for more info on logging in Cerebrum.

Typical use
------------
::

    def main(argv=None):
        parser = argparse.ArgumentParser(...)
        Cerebrum.logutils.options.install_subparser(parser)

        args = parser.parse_args(inargs)
        Cerebrum.logutils.autoconf("cronjob", args)

Use of :mod:`argparse` is recommended, but not required.  See :func:`autoconf`
for details on the ``args`` it accepts.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import inspect
import logging
import warnings
import threading

from . import config
from . import loggers
from . import handlers
from . import options


LOGGER_NAME_GLOBAL = '<cerebrum>'
"""
Name of the global Cerebrum logger.

This is a legacy logger, only used from older scripts that hasn't been updated
with a proper logging setup.

These scripts will usually call :func:`.get_logger` (or
``Cerebrum.Utils.Factory.getLogger``) to configure logging.
"""

LOGGER_NAME_UNKNOWN = '<unknown>'
"""
Name of a fallback module logger.

This is a legacy logger, only used from older modules that doesn't set up and
use a module logger.

This is is used as a fallback name when using :func:`.get_logger` (or
``Cerebrum.Utils.Factory.getLogger``) to get an unnamed logger object.
"""


_global_logger = None
_get_logger_lock = threading.Lock()

_global_config = None
_configured = False
_install_lock = threading.Lock()


def _install():
    """
    Install the CerebrumLogger into the logging module.

    Replaces :class:`logging.Logger` with the :class:`.loggers.CerebrumLogger`
    as the default logger class, and adds custom debug log levels.

    This is legacy functionality - all Cerebrum code should work with the
    generic ``logging.Logger``, and no code should use custom log levels.

    This is only done for compatibility with older code that has not been
    re-written.
    """
    with _install_lock:
        if not getattr(_install, 'installed', False):
            loggers.CerebrumLogger.install()
            setattr(_install, 'installed', True)
            return True
        return False


def get_logger(name=None, _stacklevel=2):
    """
    Legacy utility for autoconfiguring cerebrum-logging.

    .. warning::
       This function is deprecated.

    This is a legacy function that will do one of two things, depending on the
    *name* argument:

      - If a *name* is given, the logging framework will be configured with the
        named preset (see :func:`.autoconf`), unless this has already been
        configured.  The function will then return a logger with name
        :data:`.LOGGER_NAME_GLOBAL`.

      - Without a *name*, this function will try and get the logger for the
        module of the caller function.  If stack traversal does not find a
        module name, the function will return a logger with name
        :data:`.LOGGER_NAME_UNKNOWN`.

    :param str name: A named logging preset to use with autoconf

    :rtype: logging.Logger
    :returns: A logger object.
    """
    warnings.warn(
        ('%s.get_logger() is deprecated, please use logging.getLogger()') %
        (__name__, ),
        DeprecationWarning,
        stacklevel=_stacklevel)
    if name:
        logger = _get_legacy_logger(name)
    else:
        logger = _get_module_logger(stacklevel=_stacklevel)
    return logger


def _get_module_logger(stacklevel=1):
    """
    Get the module logger of the caller.

    This function will look through the stack (up to *stacklevel* number of
    frames) to find the caller module, and return a logger for that module.

    I.e. if ``_get_module_logger`` is called from ``foo.bar.baz()``, then we
    will return ``logging.getLogger("foo.bar")``.

    If we fail to find a module name, the :data:`LOGGER_NAME_UNKNOWN` will be
    used.
    """
    caller_frame = inspect.currentframe()
    for _ in range(stacklevel):
        if caller_frame.f_back:
            caller_frame = caller_frame.f_back
        else:
            # TODO: warnings.warn() ?
            break
    caller_module = inspect.getmodule(caller_frame)
    if caller_module:
        name = caller_module.__name__
    else:
        # We use a unique name that indicates that there's something wrong with
        # fetching a logger.
        # TODO/TBD: Should we solve this differently? E.g. return the root
        # logger, and issue a warning using warnings.warn()?
        name = LOGGER_NAME_UNKNOWN
    return logging.getLogger(name)


def _get_legacy_logger(name):
    """
    Get the *global* cerebrum logger.

    The first call to this function will auto-configure loggers, and return a
    global cerebrum logger object.  Subsequent calls will only get the global
    logger.

    This is legacy behaviour, emulating the logger previously returned by the
    discontinued module `Cerebrum.modules.cerelog`.

    :param str name: Logger-preset to configure

    :rtype: logging.Logger
    :returns: A common logger object, with name :data:`.LOGGER_NAME_GLOBAL`.
    """
    global _global_logger

    # TODO: This could do with some improvements.
    with _get_logger_lock:
        if _global_logger:
            return _global_logger
        if not _configured:
            autoconf(name)
        _global_logger = logging.getLogger(LOGGER_NAME_GLOBAL)
        return _global_logger


def get_cereconf():
    """
    Get the ``cereconf`` config module.

    :rtype: object
    :returns: The cereconf module, or a generic object
    """
    try:
        import cereconf
        return cereconf
    except ImportError:
        return object()


def autoconf(name, namespace=None):
    """
    Configure logging with cli-args from *namespace*.

    Autoloads the *logenv* config (see :mod:`.config`), and merges with
    settings from *namespace* (see :mod:`.options`), and then runs
    :func:`.config.configure`.

    If no *namespace* is given, this function runs in *legacy mode*, and looks
    for logger options on :data:`sys.argv`.  See
    :func:`~.options.process_arguments` for more details.

    :param str name:
        A default logging preset to use (can be overridden by cli-arguments)

    :param namespace:
        An object with logger settings, or ``None`` for *legacy mode*.

        This is *typically* a :class:`argparse.Namespace`.
    """
    global _configured

    _install()
    # Legacy autoconf:
    #  - Try to read and remove config arguments from sys.argv
    #  - Try to fetch config from cereconf
    legacy_autoconf = namespace is None

    if legacy_autoconf:
        namespace = options.process_arguments()

    # Get options
    override_exc = getattr(namespace, options.OPTION_CAPTURE_EXC, None)
    override_warn = getattr(namespace, options.OPTION_CAPTURE_WARN, None)
    override_sentry = getattr(namespace, options.OPTION_SENTRY, None)
    logger_name = getattr(namespace, options.OPTION_LOGGER_NAME, None)
    logger_level = getattr(namespace, options.OPTION_LOGGER_LEVEL, None)
    # TODO: Implement --logger-config, to specify file rather than do a lookup?

    c = config.get_config()

    cereconf = get_cereconf()

    if legacy_autoconf:
        filters = getattr(cereconf, 'PYTHON_WARNINGS', None)
        if filters is not None:
            c.warnings.filters = filters

        logdir = getattr(cereconf, 'LOGGING_ROOT_DIR', None)
        if logdir is not None:
            c.logging.logdir = logdir

    # exception logging options
    if override_exc is not None:
        c.exceptions.enable = override_exc
    if override_warn is not None:
        c.warnings.enable = override_warn
    if override_sentry is not None:
        c.sentry.enable = override_sentry

    # Configure default values in handler classes
    # TODO: Changing a class, threading locks?
    handlers.configure(c.logging)

    config.configure(c, logger_name or name, logger_level)
    # TODO: Changing a global, should use locks?
    _configured = True


def autoconf_interactive(namespace):
    """
    Configure logging in interactive scripts with a commit flag.

    This helper function wraps :func:`autoconf` to auto-select a default logger
    preset name from ``namespace.commit``.

    It is meant for interactive scripts, and selects logger preset "tee" in
    commit-mode, or "console" in dryrun-mode.
    """
    if namespace.commit:
        preset = "tee"
    else:
        preset = "console"
    autoconf(preset, namespace)
