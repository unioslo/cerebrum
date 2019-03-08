# encoding: utf-8
""" Fetch cerebrum logger from config. """
from __future__ import absolute_import, unicode_literals

import inspect
import logging
import warnings
import threading

from . import config
from . import loggers
from . import handlers
from . import options


LOGGER_NAME_GLOBAL = '<cerebrum>'
LOGGER_NAME_UNKNOWN = '<unknown>'


_global_logger = None
_get_logger_lock = threading.Lock()

_global_config = None
_configured = False
_install_lock = threading.Lock()


def _install():
    """ install the CerebrumLogger into the logging module. """
    with _install_lock:
        if not getattr(_install, 'installed', False):
            loggers.CerebrumLogger.install()
            setattr(_install, 'installed', True)
            return True
        return False


def get_logger(name=None, _stacklevel=2):
    """ Legacy utility for autoconfiguring cerebrum-logging. """
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
    """ Get a module logger for the caller.

    This function will look through the stack (up to `stacklevel` number of
    frames) to find the caller module, and return a "module logger" for that
    module.
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
    """ Get the 'global' cerebrum logger.

    This method will:

    1. Configure the logging framework with default preset 'some-name', if not
       already configured
    2. Return a generic 'cerebrum' logger

    This is legacy behaviour, emulating the logger previously returned by the
    discontinued module `Cerebrum.modules.cerelog`.
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
    """ Apply settings from cereconf to config. """
    try:
        import cereconf
        return cereconf
    except ImportError:
        return object()


def autoconf(name, namespace=None):
    """ Run config.configure with a namespace object.

    This method ties together `options` and `config`. It reads out command line
    options, and applies them to the config. It then sets up the logging in
    Cerebrum.
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

    # Configure default values in handler classes
    # TODO: Changing a class, threading locks?
    handlers.configure(c.logging)

    config.configure(c, logger_name or name, logger_level)
    # TODO: Changing a global, should use locks?
    _configured = True
