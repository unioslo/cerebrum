# encoding: utf-8
#
# Copyright 2015-2024 University of Oslo, Norway
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
""" This module contains simple reuseable function wrappers. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import threading
import traceback
import sys
from warnings import warn as _warn
from functools import wraps


# If set to False, all debug-related wrappers are disabled.
#
# TODO: Set this from somewhere?
DEBUG = True


def memoize(callobj):
    """ Memoize[1] a callable.

    [1] <http://en.wikipedia.org/wiki/Memoize>.

    The idea is to memoize a callable object supporting rest/optional
    arguments without placing a limit on the amount of cached pairs.

    NB! keyword arguments ARE NOT supported.

    @type callobj: callable
    :param callable callobj:
        A callable object to wrap.

    :return callable:
        A wrapped callable.
    """

    cache = {}

    @wraps(callobj)
    def wrapper(*rest):
        if rest not in cache:
            cache[rest] = callobj(*rest)
        return cache[rest]

    return wrapper


class debug_wrapper(object):  # noqa: N801
    """ An abstract wrapper that can print messages to stderr.

    This wrapper keeps track on 'call depth', and indents messages printed to
    stderr to indicate this depth. Note that all wrappers that inherit from
    this wrapper shares one call depth counter.
    """

    __depth = dict()

    def __init__(self, prefix=""):
        self.__prefix = prefix

    def get_func_name(self, func):
        """ Get the function name of the wrapped function.

        :param callable func:
            The function that is getting wrapped.
        :return str:
            Returns the function name.
        """
        if self.__prefix:
            return "{}.{}".format(self.__prefix, func.__name__)
        return func.__name__

    @staticmethod
    def ident():
        return threading.current_thread().ident

    @classmethod
    def _get_call_depth(cls):
        return cls.__depth.setdefault(cls.ident(), 0)

    @classmethod
    def _set_call_depth(cls, d):
        cls.__depth[cls.ident()] = d

    @classmethod
    def _inc_call_depth(cls):
        cls._set_call_depth(cls._get_call_depth() + 1)

    @classmethod
    def _dec_call_depth(cls):
        cls._set_call_depth(max(0, cls._get_call_depth() - 1))

    @staticmethod
    def indent(s, num, indent="  "):
        lines = s.split("\n")
        return indent * num + ("\n" + indent * num).join(lines)

    @classmethod
    def _log(cls, msg):
        """ Prints a message to stderr. """
        depth = cls._get_call_depth()
        print(cls.indent(msg, depth), file=sys.stderr)

    def __call__(self, func):
        """ Creates a wrapper function. """

        if not DEBUG:
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = None
            self._inc_call_depth()
            try:
                result = func(*args, **kwargs)
            finally:
                self._dec_call_depth()
            return result
        return wrapper


class debug_call(debug_wrapper):  # noqa: N801
    """ Wrap functions to log their calls.

    Each time a decorated function gets called, lines will be printed on enter
    and exit.

    Example:
        @debug_call()
        def foo(a, b):
            return a + b

        foo(1, 3)
        # enter function foo
        # exit function foo

        @debug_call(prefix='example', args=True, ret=True)
        def bar(a, b):
            return a + b

        bar(1, 3)
        # enter function example.bar with args=(1, 3) kwargs={}
        # exit function example.bar with return=4
    """

    def __init__(self, args=False, ret=False, trace=True, **kwargs):
        super(debug_call, self).__init__(**kwargs)
        self.__log_args = args
        self.__log_ret = ret
        self.__log_trace = trace

    def __call__(self, func):
        func_name = self.get_func_name(func)
        func = super(debug_call, self).__call__(func)

        if not DEBUG:
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):
            enter_msg = "enter function {}".format(func_name)
            exit_msg = "exit function {}".format(func_name)
            result = None
            if self.__log_args:
                enter_msg += " with args={} kwargs={}".format(repr(args),
                                                              repr(kwargs))
            self._log(enter_msg)
            try:
                result = func(*args, **kwargs)
                if self.__log_ret:
                    exit_msg += " with return={}".format(repr(result))
            except Exception as e:
                if self.__log_ret:
                    exit_msg += " with exception={}".format(repr(e))
                raise
            finally:
                self._log(exit_msg)
            return result
        return wrapper


class trace_call(debug_wrapper):  # noqa: N801
    """ Wrap functions to log a traceback.

    Each time a decorated function gets called, a traceback will be printed to
    stderr.

    NOTE: Should only be used for testing.

    Usage:
        @trace_call(prefix="foo_module")
        def bar(*args):
            pass

        bar()
        # called foo_module.bar
        #   File "/path/to/foo_module.py" line NN, in <module>
        #     foo()

    """
    def __call__(self, func):
        func_name = self.get_func_name(func)
        func = super(trace_call, self).__call__(func)

        if not DEBUG:
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):
            lines = traceback.format_stack()[:-1]
            self._log("called {}:".format(func_name))
            self._log("".join(lines))
            return func(*args, **kwargs)
        return wrapper


def deprecate(extra=''):
    """ Deprecate a function.

    Example:
    >>>     @deprecate("Will be removed")
    ...     def example(a, b):
    ...         return a + b

    :param str extra:
        Extra info for the deprecation warning.
    """
    def wrapper(func):
        @wraps(func)
        def newfunc(*args, **kwargs):
            msg = "{!r} is deprecated".format(func.__name__)
            if extra:
                msg += ' ({!s})'.format(extra)
            _warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return newfunc
    return wrapper
