# encoding: utf-8
""" Capture Python warnings using a logger.

This module contains utilities to change the `warnings` module behaviour, so
that warnings are logged rather than written to stderr.

It also contains some utilities to change the `warnings` filters at runtime
(e.g. from configuration).

"""
from __future__ import absolute_import, unicode_literals

import logging
import sys
import threading
import warnings


# Backup of the default showwarnings function
DEFAULT_SHOWWARNING = warnings.showwarning
logger = logging.getLogger(__name__)

_stack_lock = threading.Lock()
_stack = []
_filter_lock = threading.Lock()


class WarningsLogger(object):
    """ Replacement function for warnings.showwarning.

    This implementation of showwarning can replace the default one, to enable
    capture warnings with a logger.
    """

    DEFAULT_LEVEL = logging.WARNING

    def __init__(self, level=DEFAULT_LEVEL):
        self.level = level

    def __call__(self, message, category, filename, lineno,
                 file=None, line=None):
        """ Replacement function for warnings.showwarning that logs warnings.

        See L{warnings.showwarning} for documentation of the arguments.
        """
        logger.log(
            self.level,
            self.formatwarning(message, category, filename, lineno))

    def __repr__(self):
        return '<{0}({1}) at 0x{2:x}>'.format(
            self.__class__.__name__,
            logging.getLevelName(self.level),
            id(self))

    @property
    def level(self):
        """ the log level to use for logged warnings. """
        try:
            return self._loglevel
        except AttributeError:
            return self.DEFAULT_LEVEL

    @level.setter
    def level(self, level):
        if isinstance(level, int):
            self._loglevel = level
        else:
            self._loglevel = logging.getLevelName(level)

    def formatwarning(self, message, category, filename, lineno):
        """ Format warning log message.

        This is our implementation of warnings.formatwarning -- and makes it
        possible to override the default formatting behaviour by inheritance.

        This formatter discards the source line to prevent multiline log
        messages.
        """
        return warnings.formatwarning(
            message, category, filename, lineno, '').strip()


def set_showwarning(func=None):
    """ Replace the L{warnings.showwarning} implementation.

    :type func: callable or None
    :param func:
        A new function to use as warnings.showwarning, or None to reset to
        previous implementation.

    :raise TypeError: If L{func} is not None or callable
    """

    with _stack_lock:
        if func is None:
            try:
                warnings.showwarning = _stack.pop()
            except IndexError:
                warnings.showwarning = DEFAULT_SHOWWARNING
        elif callable(func):
            _stack.append(warnings.showwarning)
            # PY2: warn_explicit fails when warnings.showwarning is a callable
            # object:
            if sys.version_info[0] < 3 and hasattr(func, '__call__'):
                func = func.__call__
            warnings.showwarning = func
        else:
            raise TypeError("Bad showwarning function {0}".format(repr(func)))


class _FilterManager(object):
    """ Singleton object that manages custom filter rules.

    This object resets the global filter rules, then adds back the custom rules
    of this manager and the rules given in sys.warnoptions.
    """

    def __init__(self):
        self._warnoptions = None

    @property
    def warnoptions(self):
        """ Filter options added by this manager. """
        return list(self._warnoptions or ())

    def __set_filters(self, filters):
        with _filter_lock:
            filters = list(filters or ())  # Make a copy
            warnings.resetwarnings()
            for wf in filters + sys.warnoptions:
                try:
                    warnings._setoption(wf)
                except warnings._OptionError as e:
                    raise ValueError(
                        "Invalid warning filter ({0}): {1}".format(wf, e))
            return filters

    def set_filters(self, filters=None):
        if self._warnoptions is not None and self.warnoptions == filters:
            # No change
            return
        try:
            self._warnoptions = self.__set_filters(filters)
        except ValueError:
            # reset to previously working set
            self.__set_filters(self.warnoptions)
            raise


filters = _FilterManager()


if __name__ == '__main__':
    # A short demo (TODO: improve examples)
    logging.basicConfig(level=logging.DEBUG)
    filters.set_filters([
        'always:',
    ])
    set_showwarning(WarningsLogger(logging.INFO))

    def warn(msg):
        # Same code line
        warnings.warn(msg)

    warn("foo")
    warnings.warn("foo")
    warn("foo")
    warn("bar")
    warnings.warn(RuntimeWarning("foo"))
