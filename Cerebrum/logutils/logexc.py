# encoding: utf-8
""" Capture unhandled Python exceptions using a logger.

This module contains utilities to replace the default exception hook with one
that logs unhandled exceptions.

"""
from __future__ import absolute_import, unicode_literals

import logging
import sys
import threading

logger = logging.getLogger(__name__)

_stack_lock = threading.Lock()
_stack = []


class ExceptionLoggerHook(object):
    """ Replacement function for sys.__excepthook__.

    This excepthook implementation can replace the default one to capture
    unhandled exceptions with a logger.
    """

    DEFAULT_LEVEL = logging.CRITICAL

    def __init__(self, level=DEFAULT_LEVEL):
        self.level = level

    def __call__(self, *args):
        """ Replacement excepthook function. """
        try:
            logger.log(self.level, "Uncaught exception", exc_info=args)
        except:
            sys.__excepthook__(*args)

    def __repr__(self):
        return '<{0}({1}) at 0x{2:x}>'.format(
            self.__class__.__name__,
            logging.getLevelName(self.level),
            id(self))

    @property
    def level(self):
        """ the log level to use for logged exceptions. """
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


def set_exception_hook(hook=None):
    """ Set up error handler.

    :type hook: callable or None
    :param hook: A new function to use as sys.excepthook, or None to reset.

    :raise TypeError: If L{hook} is not None or callable

    """
    with _stack_lock:
        if hook is None:
            try:
                sys.excepthook = _stack.pop()
            except IndexError:
                sys.excepthook = sys.__excepthook__
        elif callable(hook):
            _stack.append(sys.excepthook)
            sys.excepthook = hook
        else:
            raise TypeError("Bad exception hook %r" % hook)


if __name__ == '__main__':
    # A short demo
    logging.basicConfig(level=logging.DEBUG)
    set_exception_hook(ExceptionLoggerHook(logging.ERROR))
    logger.info("Stack: {0}".format(repr(_stack)))
    logger.info("Current: {0}".format(repr(sys.excepthook)))
    raise Exception("Test exception")
