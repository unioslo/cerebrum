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

Logging in multiprocessing applications
=======================================

The challenge with Python, logging and multiprocessing is that there are no
locks between processes when accessing log handler resources (e.g. log files).

This library tries to fix that by providing a set of tools that allows
multiprocessing programs to set up the following logging structure:


- Main process configures logging however it likes, and starts a thread that
  listens for log records on a shared ipc *channel*, and processes the log
  records according to configuration.

- Subprocesses resets all log configuration so that:
  - All loggers propagate their log messages up to the root logger
  - The root logger handles log messages by sending them out on a shared
    *channel*


Module overview
---------------

channel
    Implementation of IPC between processes.

    The only channel implementation is currently the ``QueueChannel``, which
    uses managed ``Queue.Queue`` objects or ``multiprocessing.queues.Queue``
    objects.

handlers
    Log handlers that sends serialized log records to a *channel*.

protocol
    Utilities to serialize and deserialize log records (``logging.LogRecord``
    objects).

threads
    Generic implementations of logger threads for use in the process
    responsible for logging.  The logger threads are responsible for monitoring
    the *channel* and handling any log records.
"""
from __future__ import print_function

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
