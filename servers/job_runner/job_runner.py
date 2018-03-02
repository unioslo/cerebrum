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
import sys
import threading
import time

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.logutils import autoconf
from Cerebrum.logutils.loggers import CerebrumLogger
from Cerebrum.logutils.options import install_subparser
from Cerebrum.modules.job_runner.job_actions import LockFile, LockExists
from Cerebrum.modules.job_runner.job_utils import SocketHandling, JobQueue
from Cerebrum.modules.job_runner.job_utils import import_file, import_module

# enforce the CerebrumLogger log levels
CerebrumLogger.install()

# increase time by N seconds every second
debug_time = 0

# trap missing SIGCHLD (known race-condition, see comment in run_job_loop)
noia_sleep_seconds = 70

max_sleep = 60
current_time = time.time()

logger = logging.getLogger('job_runner')
runner_cw = threading.Condition()


def sigchld_handler(signum, frame):
    """Sigchild-handler that wakes the main-thread when a child exits"""
    logger.debug2("sigchld_handler(%r, %r)", signum, frame)
    signal.signal(signal.SIGCHLD, sigchld_handler)


signal.signal(signal.SIGCHLD, sigchld_handler)


class JobRunner(object):

    def __init__(self, job_queue):
        self.my_pid = os.getpid()
        self.timer_wait = None
        signal.signal(signal.SIGUSR1, JobRunner.sig_general_handler)
        self.job_queue = job_queue
        self._should_quit = False
        self._should_kill = False
        self.sleep_to = None
        self.queue_paused_at = 0
        self.queue_killed_at = 0
        self._last_pause_warn = 0

    @staticmethod
    def sig_general_handler(signum, frame):
        """General signal handler, for places where we use signal.pause()"""
        logger.debug2("siggeneral_handler(%s)" % (str(signum)))

    def signal_sleep(self, seconds):
        # SIGALRM is already used by the SocketThread, se we arrange
        # for a SIGUSR1 to be delivered instead
        runner_cw.acquire()
        if not self.timer_wait:  # Only have one signal-sleep thread
            logger.debug("Signalling sleep: %s seconds" % str(seconds))
            self.timer_wait = threading.Timer(seconds, self.wake_runner_signal)
            self.timer_wait.setDaemon(True)
            self.timer_wait.start()
            self.sleep_to = time.time() + seconds
        else:
            logger.debug("already doing a signal sleep")
        runner_cw.release()

    def handle_completed_jobs(self):
        """Handle any completed jobs (only jobs that has
        call != None).  Will block if any of the jobs has wait=1"""
        did_wait = False

        logger.debug("handle_completed_jobs: ")
        for job in self.job_queue.get_running_jobs():
            try:
                ret = job['call'].cond_wait(job['pid'])
            except OSError, msg:
                if not str(msg).startswith("[Errno 4]"):
                    # 4 = "Interrupted system call", which we may get
                    # as we catch SIGCHLD
                    # TODO: We need to filter out false positives from being
                    # logged:
                    logger.error("error (%s): %s" % (job['name'], msg))
                time.sleep(1)
                continue
            logger.debug2("cond_wait(%s) = %s" % (job['name'], ret))
            if ret is None:          # Job not completed
                job_def = self.job_queue.get_known_job(job['name'])
                if job_def.max_duration is not None:
                    run_for = time.time() - job['started']
                    if run_for > job_def.max_duration:
                        # We sleep a little so that we don't risk entering
                        # a tight loop with lots of logging
                        time.sleep(1)
                        logger.error("%s (pid %d) has run for %d seconds, "
                                     "sending SIGTERM" %
                                     (job['name'], job['pid'], run_for))
                        try:
                            os.kill(job['pid'], signal.SIGTERM)
                            # By setting did_wait to True, the main loop
                            # will immediately call this function again to
                            # reap the job we just killed.  (If we don't,
                            # the SIGCHLD may be delivered before we reach
                            # sigpause)
                            did_wait = True
                        except OSError as msg:
                            # Don't die if we're not allowed to kill
                            # the job. The reason is probably that the
                            # process is run by root (sudo)
                            logger.error("Couldn't kill job %s (pid %d): %s" %
                                         (job['name'], job['pid'], msg))
            else:
                did_wait = True
                if isinstance(ret, tuple):
                    if os.WIFEXITED(ret[0]):
                        msg = "exit_code=%i" % os.WEXITSTATUS(ret[0])
                    else:
                        msg = "exit_status=%i" % ret[0]
                    logger.error("%s for %s, check %s",
                                 msg, job['name'], ret[1])
                self.job_queue.job_done(job['name'], job['pid'])
        return did_wait

    def wake_runner_signal(self):
        logger.debug("Waking up")
        os.kill(self.my_pid, signal.SIGUSR1)

    def quit(self):
        self._should_kill = True
        self._should_quit = True
        self.wake_runner_signal()

    def process_queue(self, queue, num_running, force=False):
        completed_nowait_job = False
        delta = None

        if self.queue_paused_at > 0:

            if self.queue_paused_at > self._last_pause_warn:
                self._last_pause_warn = self.queue_paused_at

            if time.time() > (self._last_pause_warn +
                              cereconf.JOB_RUNNER_PAUSE_WARN):
                logger.warn("Job runner has been paused for %s hours",
                            time.strftime('%H:%M.%S',
                                          time.gmtime(time.time() -
                                                      self.queue_paused_at)))
                self._last_pause_warn = time.time()

        for job_name in queue:
            job_ref = self.job_queue.get_known_job(job_name)
            if not force:
                if self.queue_paused_at > 0:
                    delta = max_sleep
                    break
                if (job_ref.call and job_ref.call.wait and
                        num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                    # This is a minor optimalization that may be
                    # skipped.  Hopefully it makes the log easier to
                    # read
                    continue
                if self.job_queue.has_queued_prerequisite(job_name):
                    logger.debug2("has queued prereq: %s", job_name)
                    continue
                if self.job_queue.has_conflicting_jobs_running(job_name):
                    # "Abort" the job for now, but let it remain in
                    # the queue for re-evaluation the next time around
                    logger.debug2("has conflicting job(s) running: %s",
                                  job_name)
                    continue
            logger.debug("  ready: %s (force: %s)", job_name, force)

            if job_ref.call is not None:
                logger.debug("  exec: %s, # running_jobs=%i",
                             job_name, len(self.job_queue.get_running_jobs()))
                if (not force and job_ref.call.wait and
                        num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                    logger.debug("  too many paralell jobs (%s/%i)",
                                 job_name, num_running)
                    continue
                if job_ref.call.setup():
                    child_pid = job_ref.call.execute()
                    self.job_queue.job_started(job_name,
                                               child_pid,
                                               force=force)
                    if job_ref.call.wait:
                        num_running += 1
            # Mark jobs that we should not wait for as completed
            if job_ref.call is None or not job_ref.call.wait:
                logger.debug("  Call-less/No-wait job '%s' processed",
                             job_name)
                self.job_queue.job_done(job_name, None, force=force)
                completed_nowait_job = True

        return delta, completed_nowait_job, num_running

    def run_job_loop(self):
        self.jobs_has_completed = False

        while not self._should_quit:
            self.handle_completed_jobs()

            # re-fill / append to the ready to run queue.  If delay
            # queue-filling until the queue is empty, we will end up
            # waiting for all running jobs, thus reducing paralellism.
            #
            # TBD: This could in theory lead to starvation.  Is that a
            # relevant issue?

            # Run forced jobs
            tmp_queue = self.job_queue.get_forced_run_queue()
            self.process_queue(tmp_queue, -1, force=True)

            if not self.job_queue.get_run_queue():
                delta = self.job_queue.get_next_job_time()
            else:
                self.job_queue.get_next_job_time(append=True)

            # Keep track of number of running non-wait jobs
            num_running = 0
            for job in self.job_queue.get_running_jobs():
                job_ref = self.job_queue.get_known_job(job['name'])
                if job_ref.call and job_ref.call.wait:
                    num_running += 1
            logger.debug("Queue: %s", self.job_queue.get_run_queue())

            # loop modifies list:
            tmp_queue = self.job_queue.get_run_queue()[:]
            tmp_delta, completed_nowait_job, num_running = self.process_queue(
                tmp_queue, num_running)
            logger.debug("Proc Queue: '%s', '%s', '%s', delta: '%s'",
                         tmp_delta, completed_nowait_job, num_running, delta)
            if tmp_delta is not None:
                delta = tmp_delta

            # now sleep for delta seconds, or until XXX wakes us
            # because a job has completed
            # TODO: We have a race-condition here if SIGCHLD is
            # received before we do signal.pause()
            if self.handle_completed_jobs() or completed_nowait_job:
                continue     # Check for new jobs immeadeately
            if delta > 0:
                self.signal_sleep(min(max_sleep, delta))
            else:
                if not self.job_queue.get_running_jobs():
                    logger.fatal("AIEE! no running jobs and negative delta")
                    sys.exit()
                # TODO: if run_queue has a lon-running job, we should
                # only sleep until next delta.
                self.signal_sleep(noia_sleep_seconds)  # Trap missing sigchld
            logger.debug("signal.pause()")

            # continue on SIGCHLD/SIGALRM.  Won't hurt if we get another signal
            signal.pause()

            runner_cw.acquire()
            self.timer_wait.cancel()
            self.timer_wait = None
            runner_cw.release()
            logger.debug("resumed")

        if self._should_kill:
            logger.debug("Sending SIGTERM to running jobs")
            self.job_queue.kill_running_jobs()
            # ignore SIGCHLD from now on
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            logger.debug("Sleeping for 5 secs to let jobs handle signal")
            time.sleep(5)
            self.handle_completed_jobs()
            logger.debug("Sending SIGKILL to running jobs")
            self.job_queue.kill_running_jobs(signal.SIGKILL)
            time.sleep(3)
            self.handle_completed_jobs()


def get_config(name):
    if os.path.exists(name):
        return import_file(name, 'scheduled_jobs')
    else:
        return import_module(name)


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
    sock = SocketHandling(logger)
    logger.info("Sending command %r", command)
    command = command.encode('utf-8')
    try:
        return sock.send_cmd(command)
    except SocketHandling.Timeout:
        raise RuntimeError("Timout contacting server, is it running?")


def run_daemon(jobs, quiet=False, thread=True):
    """ Try to start a new job runner daemon. """
    sock = SocketHandling(logger)

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
    except SocketHandling.Timeout:
        # Assuming that previous run aborted without removing socket
        logger.warn("Socket timeout, assuming server is dead")
        try:
            os.unlink(cereconf.JOB_RUNNER_SOCKET)
        except OSError:
            pass
        pass

    # TODO: Why don't we re-aquire the lock here?

    queue = JobQueue(jobs, Factory.get('Database')(), logger)
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
    scheduled_jobs = get_config(args.config)

    if args.dump_jobs is not None:
        print("Showing jobs in {0!r}".format(scheduled_jobs))
        JobQueue.dump_jobs(scheduled_jobs, args.dump_jobs)
        raise SystemExit(0)

    logger.info("Starting daemon with jobs from %r", scheduled_jobs)
    run_daemon(scheduled_jobs)


if __name__ == '__main__':
    main()
