# -*- coding: utf-8 -*-
#
# Copyright 2015-2023 University of Oslo, Norway
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
Basic event daemon process handler.

The :class:`.ProcessHandler` is a simple class for spawning and managing
processes from :mod:`.processes`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)
import os
import ctypes
import logging
import signal
import multiprocessing
from multiprocessing import managers

from Cerebrum.logutils import mp
from Cerebrum.utils.funcwrap import memoize


class Manager(managers.BaseManager):
    """
    A SIGHUP-able shared resource manager.

    This Manager will start a SIGHUP-able subprocess to manage queues and other
    resources. On SIGHUP, the manager process will send a SIGHUP to its parent
    process.

    This manager should be used with the :class:`.ProcessHandler`, which uses
    SIGHUP to stop subprocesses.
    """

    @property
    def pid(self):
        """ The manager process PID. """
        try:
            return self._process.pid
        except AttributeError:
            return -1

    @property
    def name(self):
        """ The manager process name. """
        try:
            return self._process.name
        except AttributeError:
            return 'Manager (not started)'

    @staticmethod
    def signum_initializer(parent_pid, signums=None):
        """ Install signal handler in Server process.

        This signal handler re-sends signals to the parent process
        `parent_pid`.

        :param int parent_pid:
            The PID of the parent process of the manager server (i.e. where
            `Manager().start()` gets called from).

        :param list signums:
            A list of signals to forward to the parent process.
        """
        if signums is None:
            signums = [signal.SIGHUP]

        def sigfwd_handler(signum, frame):
            print('Manager got signal {!r}'.format(signum))
            if parent_pid is None:
                return
            if os.getpid() == parent_pid:
                return
            if signum not in signums:
                return
            os.kill(parent_pid, signum)

        for signum in signums:
            signal.signal(signum, sigfwd_handler)

    def start(self, *args, **kwargs):
        """ Cause `sighup_initializer` to run on init in Server process. """
        # TODO: Select signals to forward.
        kwargs['initializer'] = self.signum_initializer
        kwargs['initargs'] = tuple((os.getpid(), ))
        super(Manager, self).start(*args, **kwargs)


Manager.register('LogQueue', mp.threads.SizedQueue)


class ProcessHandler(object):
    """
    Simple tool for managing procesess.

    This class joins together processes from :mod:`.processes` in the following
    ways:

    Run trigger
        The handler has a shared *run trigger* to use with
        :class:`.processes.ProcessLoopMixin` processes.  The handler sets up a
        SIGHUP signal handler to toggle the *run trigger*, which should then
        *stop* these processes.

    Logging
        The handler sets up a *log queue*/*log channel* for use with
        :class:`.processes.ProcessLoggingMixin` processes.  The handler starts
        up a logger thread that processes log records from these processes.
    """

    join_timeout = 30
    """ Timeout for process and thread joins. """

    log_queue_size = 100000
    """ default maxsize for the log queue """

    log_queue_monitor_interval = 60 * 1
    """ default interval between log queue size reports """

    def __init__(self,
                 manager=Manager,
                 name='Main',
                 logger=None,
                 log_queue_size=log_queue_size,
                 log_queue_monitor_interval=log_queue_monitor_interval):
        """TODO: Is this class generic enough?

        On init the ProcessHandler will set up and start the `manager`, and a
        logging thread that logs `logutils.LogQueueRecord`s from the managers
        `log_queue`-Queue.

        :param Manager manager:
            A Manager class or subclass.
            The Manager should have the properties `queue` and `log_queue`
            after initialization.

        :param str name:
            A name for this managing process.

        :param Logger logger:
            An actual, initialized logger to use as logging backend for the log
            listener thread.
        """
        self.mgr = manager()
        self.name = name
        self.logger = logger or logging.getLogger(__name__)
        self.log_queue_size = log_queue_size
        self.procs = list()

        self.mgr.start()
        self.logger.info('Started main process (pid=%d)', os.getpid())
        self.logger.info('Started manager process (pid=%d): %s',
                         self.mgr.pid, self.mgr.name)

        self._logger_thread = mp.threads.LogRecordThread(
            self.log_channel,
            name='LogQueueListener')
        self._logger_thread.start()
        self._monitor_thread = mp.threads.QueueMonitorThread(
            self.log_queue,
            interval=self.log_queue_monitor_interval,
            name='LogQueueMonitor')
        self._monitor_thread.start()

    @property
    @memoize
    def log_queue(self):
        """ A shared queue to use for log messages. """
        return self.mgr.LogQueue(self.log_queue_size)

    @property
    @memoize
    def log_channel(self):
        serializer = mp.protocol.JsonSerializer()
        proto = mp.protocol.LogRecordProtocol(serializer)
        return mp.channel.QueueChannel(self.log_queue, proto)

    @property
    @memoize
    def run_trigger(self):
        """ A shared boolean value to signal run state. """
        return multiprocessing.Value(ctypes.c_int, 1)

    def add_process(self, process):
        self.logger.debug('Adding process: %r', process)
        self.procs.append(process)

    def print_process_list(self):
        """ Prints a list of the current processes. """
        print('Process list:')
        print('  Main({:d})'.format(os.getpid()))
        print('    {!s}({:d}): {!r}'.format(
            self.mgr.name, self.mgr.pid, self.mgr._process))
        for proc in self.procs:
            print('    {!s}({:d}): {!r}'.format(proc.name, proc.pid, proc))

    def serve(self):
        """ Start queued processes, and setup clean up tasks.

        TODO: Replace with something proper, like `atexit`.
        """
        # Start procs
        for proc in self.procs:
            proc.start()

        # SIGUSR1 - print_process_list
        def sigusr1_handle(sig, frame):
            self.print_process_list()
            signal.pause()
        signal.signal(signal.SIGUSR1, sigusr1_handle)

        # Block
        self.logger.info('Waiting for signal...')
        signal.pause()
        self.logger.info('Got signal, shutting down')

        # Stop processes and cleanup
        self.run_trigger.value = 0
        self.cleanup()

    def cleanup(self):
        """ End all processes and threads.

        This task makes sure that the subprocesses and threads started by this
        process will be terminated in the correct order.

        """
        self.logger.info('Shutting down workers...')
        for proc in self.procs:
            self.logger.debug('Waiting (max %ds) for %r',
                              self.join_timeout, proc)
            proc.join(self.join_timeout)
            log = self.logger.info if proc.exitcode == 0 else self.logger.error
            log('Process %r terminated with exit code %r', proc, proc.exitcode)

        self.logger.info('Processing remaining log records ...')
        self.log_queue.join()

        self.logger.info('Shutting down logger...')
        self._logger_thread.stop()
        self._monitor_thread.stop()
        self.logger.debug('Waiting (max %ds) for %r',
                          self.join_timeout, self._logger_thread)
        self._logger_thread.join(self.join_timeout)
        self.logger.debug('Waiting (max %ds) for %r',
                          self.join_timeout, self._monitor_thread)
        self._monitor_thread.join(self.join_timeout)

        self.logger.info('Shutting down manager...')
        self.mgr.shutdown()


def is_target_system_const(self, target_system):
    """
    Check if a `TargetSystemCode` exists in the database.

    TODO: This should *probably* be moved to the ``EventToTargetUtils`` module.
    """
    from Cerebrum.Utils import Factory
    from .EventToTargetUtils import EventToTargetUtils
    db = Factory.get('Database')()
    targets = EventToTargetUtils(db)
    try:
        int(targets._target_system_to_code(target_system))
        return True
    except Exception:
        return False


def update_system_mappings(process, target_system, change_types):
    """
    Update the target mappings for system.

    TODO: This should *probably* be moved to the ``EventToTargetUtils`` module.
    """
    from Cerebrum.Utils import Factory
    from .EventToTargetUtils import EventToTargetUtils

    logger = Factory.get_logger('cronjob')
    db = Factory.get('Database')()
    db.cl_init(change_program=process)

    targets = EventToTargetUtils(db)
    added, removed = targets.update_target_system(target_system, change_types)
    db.commit()

    if added:
        logger.info(
            'Target system %r started listening on %s',
            target_system, ', '.join([str(c) for c in added]))
    if removed:
        logger.info(
            'Target system %r stopped listening on %s',
            target_system, ', '.join([str(c) for c in removed]))
