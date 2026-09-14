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
Transport channel for log messages in multiprocess applications.

This module implements an IPC channel for sending and receiving
serialized objects.  Channels combine serialization and interprocess
communication, and if two processes use the same channel, they should be able
to send and receive supported objects between themselves.

With the right serialization, any object can be communicated, but this module
is intended for :class:`logging.LogRecord` objects.
"""
from six.moves.queue import Empty


class BaseChannel(object):
    """
    Abstract implementation of a Channel.
    """

    def _serialize(self, data):
        raise NotImplementedError("%s doesn't implement _serialize()"
                                  % repr(self))

    def _deserialize(self, data):
        raise NotImplementedError("%s doesn't implement _deserialize()"
                                  % repr(self))

    def _send(self, serialized):
        raise NotImplementedError("%s doesn't implement _send()" % repr(self))

    def _recv(self, timeout):
        raise NotImplementedError("%s doesn't implement _recv()" % repr(self))

    def send(self, message):
        """
        Send a supported object on the channel.

        :param message: A supported object to send.
        """
        self._send(self._serialize(message))

    def poll(self, timeout=None):
        """
        Poll for message on the channel.

        :param timeout:
            If timeout is ``None``, return immediately (non-blocking).
            Otherwise, block for up to *timeout* seconds before returning.

        :returns:
            The next available object from the channel, or ``None`` if no
            object is available.
        """
        raw_message = self._recv(timeout)
        if raw_message is None:
            return None
        return self._deserialize(raw_message)


class QueueChannel(BaseChannel):
    """
    Transport between processes using a queue.
    """

    def __init__(self, queue, proto):
        """
        :type queue: queue.Queue or multiprocessing.Queue
        :param queue: Shared IPC queue to use

        :type proto: protocol.LogRecordProtocol
        :param proto: Protocol for marshalling objects
        """
        self.queue = queue
        self.proto = proto

    def __repr__(self):
        return '<QueueChannel queue=%r serializer=%r>' % (self.queue,
                                                          self.proto)

    def _serialize(self, data):
        return self.proto.serialize(data)

    def _deserialize(self, data):
        return self.proto.deserialize(data)

    def _send(self, serialized):
        self.queue.put(serialized)

    def _recv(self, timeout):
        block = False if timeout is None else True
        timeout = None if timeout is None else float(timeout)

        try:
            item = self.queue.get(block=block, timeout=timeout)
        except Empty:
            item = None
        else:
            self.queue.task_done()
        return item
