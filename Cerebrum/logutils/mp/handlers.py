# -*- coding: utf-8 -*-
"""
Log handlers for multiprocessing.
"""
from __future__ import print_function, unicode_literals

import logging


class ChannelHandler(logging.Handler):
    """ Handler that put serialized ``LogRecord`` dicts onto a *channel*. """

    def __init__(self, channel):
        """
        :type channel: .channel._BaseChannel
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
