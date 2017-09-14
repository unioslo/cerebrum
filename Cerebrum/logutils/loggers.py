# encoding: utf-8
""" Cerebrum custom loggers.

This module contains the CerebrumLogger, which adds additional log levels and
associated API-methods to the python logger.

In order to use the additional API methods in a module level logger, you have to
install the logger class. This can be achieved by doing:



"""
from __future__ import absolute_import, unicode_literals

import logging
import os
from inspect import currentframe


# Additional debug levels. They will be added to the logging framework
DEBUG1 = logging.DEBUG - 1
DEBUG2 = DEBUG1-1
DEBUG3 = DEBUG2-1
DEBUG4 = DEBUG3-1
DEBUG5 = DEBUG4-1


try:
    if any(__file__.lower().endswith(ext) for ext in ['.pyc', '.pyo']):
        _srcfile = __file__[:-4] + '.py'
    else:
        _srcfile = __file__
    _srcfile = os.path.normcase(_srcfile)
except:
    _srcfile = None


class CerebrumLogger(logging.Logger, object):
    """This is the logger class used by the Cerebrum framework."""

    installed = False

    def __init__(self, name, level=logging.NOTSET):
        super(CerebrumLogger, self).__init__(name, level)

    def findCaller(self):
        """Find the stack frame of the caller.

        This function overloads the default implementation. This is so that we
        can ignore this module when looking through the call stack.

        """
        f = currentframe().f_back
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if (filename == _srcfile or
                    filename.find("logging/__init__.py") >= 0):
                f = f.f_back
                continue
            rv = (filename, f.f_lineno, co.co_name)
            break
        return rv

    def callHandlers(self, record):
        super(CerebrumLogger, self).callHandlers(record)

    def debug1(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG1):
            self._log(DEBUG1, msg, args, **kwargs)

    def debug2(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG2):
            self._log(DEBUG2, msg, args, **kwargs)

    def debug3(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG3):
            self._log(DEBUG3, msg, args, **kwargs)

    def debug4(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG4):
            self._log(DEBUG4, msg, args, **kwargs)

    def debug5(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG5):
            self._log(DEBUG5, msg, args, **kwargs)

    def set_indent(self, indent=0):
        for handle in self.handlers:
            if hasattr(handle, "set_indent"):
                handle.set_indent(indent)

    @classmethod
    def install(cls):
        for level_name in ("DEBUG1", "DEBUG2", "DEBUG3", "DEBUG4", "DEBUG5"):
            level = globals()[level_name]
            logging.addLevelName(level, level_name)
        logging.setLoggerClass(cls)
