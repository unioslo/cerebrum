# -*- encoding: utf-8 -*-
"""
Transport channel for IPC.

Channels combines serialization and interprocess communication.  If two
processes use the same channel, they should be able to send and receive
supported objects between themselves.
"""
from six.moves.queue import Empty


class _BaseChannel(object):
    """
    Abstract implementation of a Channel.
    """

    def _serialize(self, data):
        raise NotImplementedError("%s doesn't implement _serialize()")

    def _deserialize(self, data):
        raise NotImplementedError("%s doesn't implement _deserialize()")

    def _send(self, serialized):
        raise NotImplementedError("%s doesn't implement _send()")

    def _recv(self, timeout):
        raise NotImplementedError("%s doesn't implement _recv()")

    def send(self, message):
        """ Send a message on the channel. """
        self._send(self._serialize(message))

    def poll(self, timeout=None):
        """
        Poll for message on the channel.

        :param timeout:
            if timeout is ``None``, return immediately, otherwise block for up
            to timeout seconds before returning.

        :returns:
            The next available object from the channel, or ``None`` if no
            object is available.
        """
        raw_message = self._recv(timeout)
        if raw_message is None:
            return None
        return self._deserialize(raw_message)


class QueueChannel(_BaseChannel):
    """ Transport between processes using a multiprocessing.Queue. """

    def __init__(self, queue, proto):
        """
        :param queue: queue for ipc
        :param proto: protocol for serializing objects.
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
