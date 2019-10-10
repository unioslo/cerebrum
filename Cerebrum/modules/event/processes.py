# -*- encoding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA
""" This module contains common multiprocessing.Process implementations. """
from __future__ import print_function

import os
import time
import signal
import ctypes
import logging
import multiprocessing
from multiprocessing.sharedctypes import Synchronized
from Queue import Empty
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.logutils.mp import ChannelHandler
from Cerebrum.logutils.mp.utils import reset_logging


class ProcessBase(multiprocessing.Process):
    """ Common functionality for all processes. """

    def __init__(self, *args, **kwargs):
        daemon = kwargs.pop('daemon', None)
        super(ProcessBase, self).__init__(*args, **kwargs)
        if daemon is not None:
            self.daemon = bool(daemon)
        # else, do not explicitly set (inherit from parent process)

    @property
    def _key(self):
        """ A unique string hex id for this process. """
        return 'CB{:x}'.format(os.getpid()).upper()

    @property
    def _started(self):
        """ If this process has started.

        NOTE: Parent process/other procs should use `is_alive()` for this
        purpose.
        """
        return os.getpid() != self._parent_pid

    def run(self):
        """ Process runtime method. """
        try:
            self.setup()
            self.main()
        finally:
            self.cleanup()

    def setup(self):
        """ A no-op setup method. """
        return

    def cleanup(self):
        """ A no-op cleanup method. """
        return

    def main(self):
        """ A no-op main method. """
        return


class ProcessLoggingMixin(ProcessBase):
    """ Mixin to supply a QueueLogger logging object for processes.

    The log records should be processed in a LogRecordThread, running
    in the main process of your multiprocessing script.

    Example
    -------
    ::
        class MyClass(ProcessLoggingMixin):
            def main(self):
                super(MyClass, self).main()
                self.logger.info('Process {!r} is done', self.name)
        proc = MyClass(log_channel=QueueChannel(...))
        proc.start()

    """

    def __init__(self, log_channel=None, **kwargs):
        """ Initialize process with a logger.

        :param log_channel:
            A Cerebrum.modules.mp.channel._BaseChannel implementation.
        """
        super(ProcessLoggingMixin, self).__init__(**kwargs)
        self._handler = ChannelHandler(log_channel)

        # Get our custom logger as self.logger, for compability reasons
        self.logger = logging.getLogger(__name__)

    def setup(self):
        super(ProcessLoggingMixin, self).setup()

        # re-configure root logger after the new process has forked, with a
        # handler that ships data to self._log_queue
        reset_logging()
        root = logging.getLogger()
        root.addHandler(self._handler)

        self.logger.info('Process starting (pid=%r): %s',
                         os.getpid(), repr(self))

    def cleanup(self):
        self.logger.info('Process stopping (pid=%r): %s',
                         os.getpid(), repr(self))
        super(ProcessLoggingMixin, self).cleanup()


class ProcessLoopMixin(ProcessBase):
    """ Simple Process with a shared `running` kill switch.

    This Process will call `self.process()` as long as `self.running` is
    `True`.

    `self.process()` should block if nothing needs to be done, but should never
    block for more than `self.timeout` seconds.

    Example
    -------
    >>> class MyClass(ProcessLoopMixin):
    ...     def process(self):
    ...         print('Waiting {:d} seconds'.format(self.timeout))
    ...         time.sleep(self.timeout)
    >>> proc = MyClass(running=multiprocessing.Value(ctypes.c_int, 1))
    >>> proc.start()

    The process can be killed in tree ways:

    1. Set the running property to `False`
    2. Set the shared `running` value to `0` from another process
    3. Send a `SIGHUP` to this process.

    In all three cases, the shared `running` value will be set to `0`.

    If the process receives a SIGHUP, it will also pass it on to the parent
    process.

    """

    timeout = 5
    """ A timeout for the process loop. """

    def __init__(self, running=None, keep_sighup=False, **kwargs):
        """ Initializes the process loop.

        :type running:
            multiprocessing.Value(ctypes.c_int), NoneType
        :param running:
            A shared c_int Value object. The value of this object will
            determine the value of the `running` property (1,0 maps to
            True,False). If no `switch` value is given, a new, non-shared value
            is used.

        :type keep_sighup:
            Boolean
        :param keep_sighup:
            If True, we will not overwrite the parent process SIGHUP signal
            handler (default: False).
        """
        if isinstance(running, Synchronized):
            # TODO Check if c_int as well. 'ctypes.c_int' in repr(running)?
            self._running = running
        elif running is None:
            # A non-shared value
            self._running = multiprocessing.Value(ctypes.c_int, 1)
        else:
            raise TypeError(
                'Invalid running value {!r}, must be a'
                ' multiprocessing.Value(ctypes.c_int)'.format(type(running)))

        super(ProcessLoopMixin, self).__init__(**kwargs)

        # Install signal handler in *parent* process
        # TODO: Is this a good strategy? Probably not.
        signal.signal(signal.SIGHUP,
                      self.__make_ppid_sighup_handler(keep_sighup))

    @property
    def running(self):
        """ A (shared) boolean killswitch value. """
        return bool(self._running.value)

    @running.setter
    def running(self, value):
        self._running.value = int(bool(value))

    def __make_ppid_sighup_handler(self, keep_parent):
        """ Make signal handler for parent process. """
        if keep_parent:
            old_handler = signal.getsignal(signal.SIGINT)
        else:
            old_handler = None

        def handler(signum, frame):
            """ Sets `running` to False on SIGHUP. """
            print('Parent (main) process got SIGHUP')
            self.running = False
            if callable(old_handler):
                old_handler(signum, frame)
        return handler

    def __sighup_handler(self, signum, frame):
        """ Sets `running` to False on SIGHUP. """
        print(self.name, 'got SIGHUP')
        self.running = False
        if os.getpid() != self._parent_pid:
            os.kill(self._parent_pid, signum)

    def setup(self):
        super(ProcessLoopMixin, self).setup()

        # Set up SIGHUP handler in forked process
        signal.signal(signal.SIGHUP, self.__sighup_handler)

    def main(self):
        super(ProcessLoopMixin, self).main()
        while self.running:
            self.process()

    def process(self):
        """ Implementation of the process loop. """
        time.sleep(self.timeout)


class ProcessDBMixin(ProcessBase):
    """ Mixin to supply db objects to a process. """

    db_enc = 'utf-8'
    """ Database encoding. """

    def __init__(self, dryrun=False, **kwargs):
        """ Initialize process.

        :param bool dryrun:
            If True, commit will be disabled in the db object (default: False).
        """
        self._db_dryrun = dryrun
        super(ProcessDBMixin, self).__init__(**kwargs)

    @property
    @memoize
    def db(self):
        """ The database connection. """
        if not self._started:
            raise RuntimeError('Tried to set up database connection pre-fork')
        db = Factory.get('Database')(client_encoding=self.db_enc)
        if self._db_dryrun:
            # TODO: Wrap the rollback-commit in something that issues a warn?
            db.commit = db.rollback
        return db

    @property
    @memoize
    def co(self):
        """ Constants. """
        return Factory.get('Constants')(self.db)

    @property
    @memoize
    def clconst(self):
        """ CLConstants. """
        return Factory.get('CLConstants')(self.db)


class ProcessQueueMixin(ProcessBase):
    """ Simple multiprocessing queue handler. """

    def __init__(self, queue=None, fan_out_queues=None, **kwargs):
        """EventHandler initialization routine.

        :param Queue queue:
            The queue to poll or put items on.
        :param list fan_out_queues:
            A list of additional queues to put items on.
        """
        self.queues = fan_out_queues or []
        self.queue = queue
        if queue:
            self.queues.append(queue)
        super(ProcessQueueMixin, self).__init__(**kwargs)

    def push(self, item):
        """ Pushes an item on the shared queue.

        :param item:
            Any pickleable object.
        """
        for queue in self.queues:
            queue.put(item)


class QueueListener(ProcessQueueMixin, ProcessLoopMixin):
    """ An abstract queue listener process. """
    def process(self):
        try:
            item = self.queue.get(block=True, timeout=self.timeout)
        except Empty:
            return
        self.handle(item)

    def handle(self, item):
        raise NotImplementedError('{!r}.handle not implemented'.format(self))
