# -*- coding: utf-8 -*-
"""
Utilities for configuring up loggers with multiprocessing.
"""
import logging


def reset_logger(logger):
    """ Reset a logger.  """
    old_handlers = getattr(logger, "handlers", None) or []

    logger.level = logging.NOTSET
    logger.handlers = []
    logger.propagate = True
    logger.disabled = False

    for handler in old_handlers:
        try:
            handler.close()
        except Exception:
            pass


def reset_logging():
    """ Reset all known loggers. """
    root = logging.getLogger()
    reset_logger(root)
    for logger in root.manager.loggerDict.values():
        reset_logger(logger)
