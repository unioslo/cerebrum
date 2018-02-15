#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" Basic event daemon process handler.

The ProcessHandler is a simple class that helps spawning processes and threads.
"""
from __future__ import print_function
import os
import ctypes
import logging
import signal
import multiprocessing
from multiprocessing import managers
from Cerebrum.utils.funcwrap import memoize

from . import logutils


class Manager(managers.BaseManager):
    """ A SIGHUP-able shared resource manager.

    This Manager will start a SIGHUP-able subprocess to manage queues and other
    resources. On SIGHUP, the manager process will send a SIGHUP to its parent
    process.

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
    def signum_initializer(parent_pid, signums=[signal.SIGHUP, ]):
        """ Install signal handler in Server process.

        This signal handler re-sends signals to the parent process
        `parent_pid`.

        :param int parent_pid:
            The PID of the parent process of the manager server (i.e. where
            `Manager().start()` gets called from).

        :param list signums:
            A list of signals to forward to the parent process.
        """
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


Manager.register('log_queue', multiprocessing.Queue)


class ProcessHandler(object):
    """ Simple tool for starting a list of processes. """

    join_timeout = 30
    """ Timeout for process and thread joins. """

    def __init__(self, manager=Manager, name='Main', logger=None):
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
        self.name = name
        self.procs = list()
        self.mgr = manager()

        self.mgr.start()
        self.logger = logger or logging.getLogger(__name__)

        self.logger.info('Started main process (pid=%d)', os.getpid())
        self.logger.info('Started manager process (pid=%d): %s',
                         self.mgr.pid, self.mgr.name)

        self.__log_th = logutils.LogRecordThread(logger=logger,
                                                 queue=self.log_queue,
                                                 name='LogQueueListener')
        self.__log_th.start()

    @property
    @memoize
    def log_queue(self):
        """ A shared queue to use for log messages. """
        return self.mgr.log_queue()

    @property
    @memoize
    def run_trigger(self):
        """ A shared boolean value to signal run state. """
        return multiprocessing.Value(ctypes.c_int, 1)

    def add_process(self, cls, *args, **kwargs):
        """ Queues a process to start when calling `serve`. """
        proc = cls(*args, **kwargs)
        proc.daemon = True
        self.logger.debug('Adding process: %r', proc)
        self.procs.append(proc)

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

        # Cleanup
        self.run_trigger.value = 0
        self.cleanup()

    def cleanup(self):
        """ End all processes and threads.

        This task makes sure that the subprocesses and threads started by this
        process will be terminated in the correct order.

        """
        for proc in self.procs:
            self.logger.debug('Waiting (max %ds) for process %r',
                              self.join_timeout, proc)
            proc.join(self.join_timeout)
            # Log result
            log_args = ('Process %s terminated with exit code %d',
                        proc,
                        proc.exitcode)
            if proc.exitcode == 0:
                self.logger.debug(*log_args)
            else:
                self.logger.warn(*log_args)

        self.logger.debug('Shutting down logger...')

        self.__log_th.stop()
        self.__log_th.join(self.join_timeout)

        # Shut down manager
        self.mgr.shutdown()


def is_target_system_const(self, target_system):
    """ Check if a `TargetSystemCode` exists in the database. """
    from Cerebrum.Utils import Factory
    from .EventToTargetUtils import EventToTargetUtils
    db = Factory.get('Database')()
    targets = EventToTargetUtils(db)
    try:
        int(targets._target_system_to_code(target_system))
        return True
    except:
        return False


def update_system_mappings(process, target_system, change_types):
    """ Update the target mappings for system. """
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
