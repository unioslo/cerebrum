# -*- coding: utf-8 -*-

# Copyright 2004-2018 University of Oslo, Norway
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
""" Job Runner daemon - the Cerebrum scheduler.

cereconf
--------

JOB_RUNNER_PAUSE_WARN
    Warn if job runner has been paused for more than N seconds, every N
    seconds.

JOB_RUNNER_MAX_PARALELL_JOBS
    Max number of jobs to run off the job queue.

# Not here:
JOB_RUNNER_SOCKET
    The socket used to communicate with Job Runner (in socket_ipc)

JOB_RUNNER_LOG_DIR
    The job runner temp dir (in job_actions), used for:

    - Job output (stdout, stderr)
    - Job lock files
"""
import logging
import os
import signal
import threading
import time

from .times import fmt_time

import cereconf

# mod_job_runner version
__version__ = '1.2'

logger = logging.getLogger(__name__)
runner_cw = threading.Condition()


def sigchld_handler(signum, frame):
    """Sigchild-handler that wakes the main-thread when a child exits"""
    # logger.debug("sigchld_handler(%r, %r)", signum, frame)
    signal.signal(signal.SIGCHLD, sigchld_handler)


def sig_general_handler(signum, frame):
    """ General signal handler, for places where we use signal.pause()"""
    # logger.debug("siggeneral_handler(%r, %r)" % (signum, frame))
    pass


class JobRunner(object):

    max_sleep = 60

    # trap missing SIGCHLD (known race-condition, see comment in run_job_loop)
    noia_sleep_seconds = 70

    def __init__(self, job_queue):
        self.my_pid = os.getpid()
        self.timer_wait = None
        signal.signal(signal.SIGUSR1, sig_general_handler)
        self.job_queue = job_queue
        self._should_quit = False
        self._should_kill = False
        self.sleep_to = None
        self.queue_paused_at = 0
        self.queue_killed_at = 0
        self._last_pause_warn = 0

    def signal_sleep(self, seconds):
        # SIGALRM is already used by the SocketThread, se we arrange
        # for a SIGUSR1 to be delivered instead
        logger.debug("starting timer")
        runner_cw.acquire()
        if not self.timer_wait:  # Only have one signal-sleep thread
            logger.info("Signalling sleep: %r seconds", seconds)
            self.timer_wait = threading.Timer(seconds, self.wake_runner_signal)
            self.timer_wait.setDaemon(True)
            self.timer_wait.start()
            self.sleep_to = time.time() + seconds
        else:
            logger.info("already doing a signal sleep")
        runner_cw.release()

    def handle_completed_jobs(self):
        """Handle any completed jobs (only jobs that has call != None).

        Will block if any of the jobs has wait=1
        """
        did_wait = False

        logger.debug("handle_completed_jobs")
        for job in self.job_queue.get_running_jobs():
            try:
                ret = job['call'].cond_wait(job['pid'])
            except OSError as e:
                if e.errno == 4:
                    # 4 = "Interrupted system call", which we may get
                    # as we catch SIGCHLD
                    # TODO: We need to filter out false positives from being
                    # logged:
                    logger.debug("cond_wait(%r) interrupt %r", job['name'], e)
                else:
                    logger.error("cond_wait(%r) error %r", job['name'], e)
                time.sleep(1)
                continue
            logger.debug("cond_wait(%r) = %r" % (job['name'], ret))
            if ret is None:
                # Job not completed
                job_def = self.job_queue.get_known_job(job['name'])
                if job_def.max_duration is not None:
                    run_for = time.time() - job['started']
                    if run_for > job_def.max_duration:
                        # We sleep a little so that we don't risk entering
                        # a tight loop with lots of logging
                        time.sleep(1)
                        logger.error("{} (pid %d) has run for %d seconds, "
                                     "sending SIGTERM".format(job['name']),
                                     job['pid'], run_for)
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
                    msg, rundir = ret
                    logger.error(
                        "{} for {}, check %s".format(msg, job['name']),
                        rundir)
                    error = '{}, check {}'.format(msg, rundir)
                    if msg.startswith('exit_code=0'):
                        job_ok = True
                    else:
                        job_ok = False
                else:
                    error = None
                    job_ok = True
                self.job_queue.job_done(job['name'], job['pid'],
                                        ok=job_ok, msg=error)
        return did_wait

    def wake_runner_signal(self):
        logger.info("Waking up")
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
                            fmt_time(time.time() - self.queue_paused_at,
                                     local=False))
                self._last_pause_warn = time.time()

        for job_name in queue:
            job_ref = self.job_queue.get_known_job(job_name)
            if not force:
                if self.queue_paused_at > 0:
                    delta = self.max_sleep
                    break
                if (job_ref.call and job_ref.call.wait and
                        num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                    # This is a minor optimalization that may be
                    # skipped.  Hopefully it makes the log easier to
                    # read
                    continue
                if self.job_queue.has_queued_prerequisite(job_name):
                    logger.debug("has queued prereq: %s", job_name)
                    continue
                if self.job_queue.has_conflicting_jobs_running(job_name):
                    # "Abort" the job for now, but let it remain in
                    # the queue for re-evaluation the next time around
                    logger.debug("has conflicting job(s) running: %s",
                                 job_name)
                    continue
            logger.info("  ready: %s (force: %s)", job_name, force)

            if job_ref.call is not None:
                logger.info("  exec: %s, # running_jobs=%i",
                            job_name, len(self.job_queue.get_running_jobs()))
                if (not force and job_ref.call.wait and
                        num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                    logger.info("  too many paralell jobs (%s/%i)",
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
                logger.info("  Call-less/No-wait job '%s' processed",
                            job_name)
                self.job_queue.job_done(job_name, None, force=force)
                completed_nowait_job = True

        return delta, completed_nowait_job, num_running

    def run_job_loop(self):
        self.jobs_has_completed = False

        while not self._should_quit:
            logger.debug("job_runner main loop run")
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
            logger.info("Queue: %s", self.job_queue.get_run_queue())

            # loop modifies list:
            tmp_queue = self.job_queue.get_run_queue()[:]
            tmp_delta, completed_nowait_job, num_running = self.process_queue(
                tmp_queue, num_running)
            logger.info("Proc Queue: '%s', '%s', '%s', delta: '%s'",
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
                self.signal_sleep(min(self.max_sleep, delta))
            else:
                if not self.job_queue.get_running_jobs():
                    logger.error("No running jobs and negative wait until "
                                 "next job (delta=%r)", delta)
                # TODO: if run_queue has a lon-running job, we should
                # only sleep until next delta.
                # Trap missing sigchld
                self.signal_sleep(self.noia_sleep_seconds)
            logger.info("signal.pause()")

            # continue on SIGCHLD/SIGALRM.  Won't hurt if we get another signal
            signal.pause()

            logger.debug("stopping timer")
            runner_cw.acquire()
            self.timer_wait.cancel()
            self.timer_wait = None
            runner_cw.release()
            logger.info("resumed")

        if self._should_kill:
            logger.info("Sending SIGTERM to running jobs")
            self.job_queue.kill_running_jobs()
            # ignore SIGCHLD from now on
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            logger.info("Sleeping for 5 secs to let jobs handle signal")
            time.sleep(5)
            self.handle_completed_jobs()
            logger.info("Sending SIGKILL to running jobs")
            self.job_queue.kill_running_jobs(signal.SIGKILL)
            time.sleep(3)
            self.handle_completed_jobs()
        logger.info("job_runner main loop stopping")
