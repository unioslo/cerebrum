# encoding: utf-8
"""
Custom Cerebrum loggers.


This module contains the :mod:`.CerebrumLogger`, which adds additional log
levels and associated API-methods to the :mod:`logging` module.

.. warning::
   This module is deprecated, and the custom log levels should not be used in
   new code.

   If you need to filter additional log messages, use a dedicated logger
   that can be enabled/disabled or be configured with additional filtering.

In order to use the additional API methods in a logger, you have to install the
this logger class before fetching the log object. This can be achieved by
doing:
::

    CerebrumLogger.install()

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging


# Additional debug levels. They will be added to the logging framework
DEBUG1 = logging.DEBUG - 1
""" Log level DEBUG - 1 """

DEBUG2 = DEBUG1 - 1
""" Log level DEBUG - 2 """

DEBUG3 = DEBUG2 - 1
""" Log level DEBUG - 3 """

DEBUG4 = DEBUG3 - 1
""" Log level DEBUG - 4 """

DEBUG5 = DEBUG4 - 1
""" Log level DEBUG - 5 """


class CerebrumLogger(logging.Logger, object):
    """This is the logger class used by the Cerebrum framework."""

    installed = False

    def __init__(self, name, level=logging.NOTSET):
        super(CerebrumLogger, self).__init__(name, level)

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
        """ pass indent to any `IdentField` filters in handlers. """
        # TODO: Deprecate this insanity
        self._indent = max(0, int(indent))

    def makeRecord(self, *args, **kwargs):  # noqa: N802
        r = super(CerebrumLogger, self).makeRecord(*args, **kwargs)
        setattr(r, 'indent', getattr(self, '_indent', 0))
        return r

    @classmethod
    def install(cls):
        for level_name in ("DEBUG1", "DEBUG2", "DEBUG3", "DEBUG4", "DEBUG5"):
            level = globals()[level_name]
            logging.addLevelName(level, level_name)
        logging.setLoggerClass(cls)
