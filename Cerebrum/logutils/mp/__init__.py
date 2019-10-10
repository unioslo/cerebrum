# -*- encoding: utf-8 -*-
#
# Copyright 2015-2019 University of Oslo, Norway
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
This module contains simple multiprocess logging tools.
"""
from __future__ import print_function

import logging
import multiprocessing

from six.moves.queue import Queue


class LogQueue(Queue):
    """ A Queue.Queue object with access to the maxsize attribute.

    Proxied objects (from a multiprocessing.manager.BaseManager) does not
    expose attributes, only methods. This class exposes the maxsize attribute
    through a method.
    """
    def get_maxsize(self):
        return self.maxsize


class ChannelHandler(logging.Handler):
    """ Handler that sticks serialized `LogRecord` dicts onto a 'channel'. """

    def __init__(self, channel):
        """
        :type channel: _BaseChannel
        """
        if channel is None:
            raise ValueError("invalid channel")
        self.channel = channel
        super(ChannelHandler, self).__init__()

    def send(self, record):
        # TODO: Copy error handling from logging.handlers.SocketHandler?
        self.channel.send(record)

    def emit(self, record):
        try:
            self.send(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

    def close(self):
        pass


def get_stderr_logger(level=multiprocessing.SUBDEBUG):
    lug = multiprocessing.log_to_stderr()
    lug.setLevel(level)
    return lug
