#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
"""job_runner is a scheduler that runs specific commands at certain times.

Each command is represented by an Action class that may have
information about when and how often a job should be run, as well as
information about jobs that should be run before or after itself; see
the class documentation for details.

job_runner has a ready_to_run queue, which is populated by
find_ready_jobs().  The queue is recursively populated so that pre and
post requisites are added in the correct order.  This could lead to
the same job being listed multiple times in the queue, therefore we
check for this before adding the job (unless overridden in the
constructor).

TODO:
- should we do anything more than simply logging an error message when
  a job failes?
- locking
- start specific actions from the commandline, optionally with
  verbosity or dryrun arguments (should add job, ignoring max_freq)
- Support jobs represented by a call to a specific method in given
  python module
- commandline option to start job_runner if it is not already running
- running multiple jobs in parallel, in particular manually added jobs
  should normally start immediately
"""

# TBD: Paralellitet: dersom det er flere jobber i ready_to_run køen
# som ikke har noen ukjørte pre-requisites, kan de startes samtidig.

import argparse
import logging
import os
import signal
import threading

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.logutils import autoconf
from Cerebrum.logutils.options import install_subparser
from Cerebrum.modules.job_runner import JobRunner, sigchld_handler
from Cerebrum.modules.job_runner.job_actions import LockFile, LockExists
from Cerebrum.modules.job_runner.job_config import get_job_config, dump_jobs
from Cerebrum.modules.job_runner.queue import JobQueue
from Cerebrum.modules.job_runner.socket_ipc import (SocketHandling,
                                                    SocketTimeout)

logger = logging.getLogger('job_runner')

signal.signal(signal.SIGCHLD, sigchld_handler)


def make_parser():
    parser = argparse.ArgumentParser(
        description="Start a job runner daemon, or send command to daemon")

    halt = getattr(cereconf, 'HALT_PERIOD', 0)

    parser.add_argument(
        '--quiet',
        dest='quiet',
        action='store_true',
        default=False,
        help='exit silently if another server is already running')

    config = parser.add_mutually_exclusive_group()
    config.add_argument(
        '--config',
        dest='config',
        metavar='NAME',
        default='scheduled_jobs',
        help='use alternative config (filename or module name)')

    commands = parser.add_mutually_exclusive_group()

    commands.add_argument(
        '--reload',
        dest='command',
        action='store_const',
        const='RELOAD',
        help='re-read the config file')

    commands.add_argument(
        '--quit',
        dest='command',
        action='store_const',
        const='QUIT',
        help='exit gracefully (allow current jobs to complete)')

    commands.add_argument(
        '--kill',
        dest='command',
        action='store_const',
        const='KILL',
        help='exit, but kill jobs not finished after %d seconds' % halt)

    commands.add_argument(
        '--status',
        dest='command',
        action='store_const',
        const='STATUS',
        help='show status for a running job-runner')

    commands.add_argument(
        '--pause',
        dest='command',
        action='store_const',
        const='PAUSE',
        help='pause the queue, i.e. don\'t start any new jobs')

    commands.add_argument(
        '--resume',
        dest='command',
        action='store_const',
        const='RESUME',
        help='resume from paused state')

    commands.add_argument(
        '--run',
        dest='run_job',
        metavar='NAME',
        help='adds %(metavar)s to the fron of the run queue'
             ' (without dependencies')

    parser.add_argument(
        '--with-deps',
        dest='run_with_deps',
        action='store_true',
        default=False,
        help='make --run honor dependencies')

    commands.add_argument(
        '--show-job',
        dest='show_job',
        metavar='NAME',
        help='show detailed information about the job %(metavar)s')

    commands.add_argument(
        '--dump',
        dest='dump_jobs',
        nargs=1,
        type=int,
        default=None,
        metavar='DEPTH',
        help='')

    commands.set_defaults(command=None)

    return parser


def run_command(command):
    sock = SocketHandling()
    command = command.encode('utf-8')
    try:
        return sock.send_cmd(command)
    except SocketTimeout:
        raise RuntimeError("Timout contacting server, is it running?")


def run_daemon(jobs, quiet=False, thread=True):
    """ Try to start a new job runner daemon. """
    sock = SocketHandling()

    # Abstract Action to get a lockfile
    # TODO: Couldn't we just use the socket to see if we're running?
    lock = LockFile('master_jq_lock')

    try:
        if sock.ping_server():
            raise SystemExit(int(quiet) or "Server already running")
        try:
            lock.acquire()
        except LockExists:
            logger.error(
                "%s: Master lock exists, but jr-socket didn't respond to "
                "ping. This should be a very rare error!",
                lock.filename)
            raise SystemExit(1)
    except SocketTimeout:
        # Assuming that previous run aborted without removing socket
        logger.warn("Socket timeout, assuming server is dead")
        try:
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
        except OSError:
            pass
        pass

    # TODO: Why don't we re-aquire the lock here?

    queue = JobQueue(jobs, Factory.get('Database')())
    runner = JobRunner(queue)

    if thread:
        socket_thread = threading.Thread(
            target=sock.start_listener,
            args=(runner, ))
        socket_thread.setDaemon(True)
        socket_thread.setName("socket_thread")
        socket_thread.start()

    runner.run_job_loop()
    logger.debug("bye")
    sock.cleanup()
    lock.release()


def main(inargs=None):
    parser = make_parser()
    install_subparser(parser)
    args = parser.parse_args(inargs)

    # autoconf('cronjob', args)
    # TODO:
    autoconf('console', args)

    logger.debug("job_runner args=%r", args)

    # TODO: Fix
    setattr(cereconf, 'JOB_RUNNER_SOCKET',
            os.path.join(os.getcwd(), 'jr.sock'))
    logger.debug("job runner socket=%r exists=%r",
                 cereconf.JOB_RUNNER_SOCKET,
                 os.path.exists(cereconf.JOB_RUNNER_SOCKET))

    command = None

    # What to do:
    if args.command:
        command = args.command
    elif args.run_job:
        command = 'RUNJOB %s %i' % (args.run_job, int(args.run_with_deps))
    elif args.show_job:
        command = 'SHOWJOB %s' % args.show_job

    if command:
        print(run_command(command))
        raise SystemExit(0)

    # Not running a command, so we'll need a config:
    scheduled_jobs = get_job_config(args.config)

    if args.dump_jobs is not None:
        print("Showing jobs in {0!r}".format(scheduled_jobs))
        dump_jobs(scheduled_jobs, args.dump_jobs)
        raise SystemExit(0)

    logger.info("Starting daemon with jobs from %r", scheduled_jobs)
    run_daemon(scheduled_jobs)


if __name__ == '__main__':
    main()
