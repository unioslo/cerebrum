# -*- encoding: utf-8 -*-
#
# Copyright 2015-2026 University of Oslo, Norway
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
Helpers for configuring loggers in multiprocess applications.
"""
import logging


def reset_logger(logger):
    """
    Reset a logger object.

    - clear level filter
    - remove and close handlers
    - set propagate flag
    - clear disabled flag

    :type logger: logging.Logger
    :param logger: A logger object to reset
    """
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
    """
    Reset all current loggers.

    Uses the :data:`logging.root.manager` to find and reset loggers with
    :func:`.reset_logger`.
    """
    root = logging.getLogger()
    reset_logger(root)
    for logger in root.manager.loggerDict.values():
        reset_logger(logger)
