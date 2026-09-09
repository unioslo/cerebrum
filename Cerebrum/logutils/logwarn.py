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
Capture Python warnings using a logger.

This module contains utilities to change the :mod:`warnings` module behaviour,
so that warnings are logged rather than written to stderr.

It also contains some utilities to change the warning filters at runtime
(e.g. from configuration).
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import sys
import threading
import warnings


#: Backupi of the default showwarnings function
DEFAULT_SHOWWARNING = warnings.showwarning

logger = logging.getLogger(__name__)

# Lock for protected access to the set_showwarning and the _stack
_stack_lock = threading.Lock()

# A stack of previous warnings.showwarning functions.  Allows resetting
# warnings.showwarning with set_showwarning(None)
_stack = []

# Lock for protected access to _FilterManager.set_filters
_filter_lock = threading.Lock()


class WarningsLogger(object):
    """ Replacement function for :func:`warnings.showwarning`.

    This callable object is a showwarning compatible function that can be used
    to capture warnings with a logger.
    """

    #: Default log level for captured warnings
    DEFAULT_LEVEL = logging.WARNING

    def __init__(self, level=DEFAULT_LEVEL):
        """
        :param int level: Log level to use for captured warnings
        """
        self.level = level

    def __call__(self, message, category, filename, lineno,
                 file=None, line=None):
        """
        showwarning callback.

        See :func:`warnings.showwarning` for argument details.
        """
        logger.log(
            self.level,
            self.formatwarning(message, category, filename, lineno, line=line))

    def __repr__(self):
        return '<{0}({1}) at 0x{2:x}>'.format(
            self.__class__.__name__,
            logging.getLevelName(self.level),
            id(self))

    @property
    def level(self):
        """ log level to use for warnings. """
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

    def formatwarning(self, message, category, filename, lineno, line=None):
        """
        Format warning log message.

        This is our implementation of :func:`warnings.formatwarning` - and
        makes it possible to override the default formatting behaviour by
        inheritance.

        This formatter discards the source line to prevent multiline log
        messages.
        """
        return warnings.formatwarning(
            message, category, filename, lineno, line).strip()


def set_showwarning(func=None):
    """ Replace :func:`warnings.showwarning`

    :type func: callable or None
    :param func:
        A new function to use as warnings.showwarning, or None to reset to
        previous implementation.

    :raise TypeError: If *func* is not None or callable
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
    """
    Singleton object for managing filter rules.

    This object manages and keeps track of two sets of filtering rules - the
    :data:`sys.warnoptions`, and its own :attr:`.warnoptions`.

    The former is typically set by environment variables or as python startup
    options, while the latter is set through code (e.g. from warning settings
    in the logenv config (:mod:`.config`).

    The manager merges the two sets of filtering rules, while only allowing the
    custom rules to be changed.
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


#: Filter rules manager
filters = _FilterManager()
"""
Filter manager.

An internal set of warnoptions that gets merged with :data:`sys.warnoptions`.

Example use:
::

    filters.set_filters(['always:'])
"""


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
