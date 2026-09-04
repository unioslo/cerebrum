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
Log utils for multiprocessing.

Logging in multiprocess applications
-------------------------------------
The challenge with logging from multiprocess applications is that there are no
locks between the processes when accessing log handler resources (e.g. log
files).

This library tries to fix that by providing a set of tools for
:mod:`multiprocessing`, to help set up the following logging structure:

Main process
    Configures logging however it likes.

    Sets up an IPC *channel* for receiving log records, and a log *thread* that
    will listen for messages, reconstruct log records, and handle them with the
    appropriate logger and log configuration.

Subprocess
    Immediately resets and reconfigures loggers after spawning.

    The new log config consists of a root logger with a handler to send out
    serialized log records on the *channel* that the main process is listening
    to.  All other loggers are set to propagate log messages to the root
    logger.

Channel
    The log *channel* is responsible for sending and receiving
    :class:`~logging.LogRecord` objects.

    The only current implementation is the :class:`~.channel.QueueChannel`,
    which uses a queue (either a :class:`multiprocessing.Queue`, or a
    managed `queue.Queue`).

    In subprocesses our :class:`.handlers.ChannelHandler` will send log records
    using the configured channel.  The channel will marshal the log record and
    put it on the queue.  On the other end, our main process will pop the
    serialized message, and reconstruct a LogRecord object.

    Record serialization is done by our :class:`.protocol.LogRecordProtocol`.
    The protocol removes unserializable fields (args and traceback), and formats
    the record as a JSON string or Pickle bytestring.

.. note::
   This strategy is similar to the one suggested in the Python HOWTO documents,
   in the :external+python:doc:`howto/logging-cookbook`.

   Our handler and listener thread are similar to the stdlib
   :class:`logging.handlers.QueueHandler` and
   :class:`logging.handlers.QueueListener`.

   The main difference between the stdlib classes and our own is how we
   abstract away the IPC *transport* in a *channel*.  This allows us to
   serialize more fields, and re-construct a :class:`~logging.LogRecord` that
   retains more information from the original record.


Example setup
--------------
Main process:
::

    # Configure logging as usual, e.g.:
    logging.basicConfig(
        format="[%(processName)s] %(levelname)s - %(name)s - %(message)s",
    )

    # Set up a queue for IPC
    log_queue = multiprocessing.Queue()

    # Configure marshalling
    log_proto = protocol.LogRecordProtocol(protocol.JsonSerializer())

    # Create a shared channel for the queue
    log_channel = channel.QueueChannel(log_queue, log_proto)

    # Start a subprocess and provide access to the shared channel.
    # This can be done with e.g. a :class:`multiprocessing.Manager`

    # Start processing incoming log records in a thread
    log_thread = threads.LogRecordThread(log_channel, timeout=1.0)


Subprocess:
::

    # reset logging
    utils.reset_logging()

    # set up log handler
    logging.getLogger().addHandler(
        handlers.ChannelHandler(log_channel))

    # log messages like normal
    logger = logging.getLogger("foo")
    logger.info("hello, main process!")


Future improvements
--------------------
Better serialization
    We could try harder to serialize values that are not normally serializable.
    For example, we could replace the ``%`` format in the message with ``%s``,
    and use ``repr()`` on individual unserializable args, rather than the
    current approach of using ``repr()`` on all args.  If we do, we should also
    consider pre-formatting a message attribute.

Filter records earlier
    We could keep the log level filtering of individual loggers, to reduce
    the number of log records sent over the IPC channel.  This would complicate
    the log setup in subprocesses, however.

Simplify the classes
    We may not need the current pattern with *abstract* base classes and
    specific implementations.  It is unlikely that we will ever need an
    alternative implementation of the *channel*.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from . import channel
from . import handlers
from . import protocol
from . import threads
from . import utils


__all__ = [
    'channel',
    'handlers',
    'protocol',
    'threads',
    'utils',
]
