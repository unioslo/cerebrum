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
Log handlers for multiprocess applications.

This module implements handlers to send log records to another process.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging


class ChannelHandler(logging.Handler):
    """
    Handler for sending log records on a *channel*.

    This handler sends the log record from a *subprocess* to a *main process*
    that should be listening for records on the same *channel*.

    See :mod:`.channel` for info on the log record serialization and IPC.
    """

    def __init__(self, channel):
        """
        :type channel: channel.BaseChannel
        :param channel: Channel to use for sending log records
        """
        if channel is None:
            raise ValueError("invalid channel")
        self.channel = channel
        super(ChannelHandler, self).__init__()

    def send(self, record):
        """
        Send the log record on the channel.

        :type record: logging.LogRecord
        :param record: The log record to send
        """
        # TODO: Copy error handling from logging.handlers.SocketHandler?
        self.channel.send(record)

    def emit(self, record):
        """
        Emit a log record using this handler.

        This is the entry point for processing a log record using a log
        handler.  See :mod:`logging` for more details.

        :type record: logging.LogRecord
        :param record: The log record to emit
        """
        try:
            self.send(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def close(self):
        # TODO: we should probably remove this method (or call
        # super().close()), so the handler registers as *closed*, and is
        # properly removed from the logging inventory...
        pass
