#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# $Id$
# TBD: Paralellitet: dersom det er flere jobber i ready_to_run køen
# som ikke har noen ukjørte pre-requisites, kan de startes samtidig.

"""job_runner is a scheduler that runs specific commands at certain
times.  Each command is represented by an Action class that may have
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

import time
import os
import sys
import popen2
import fcntl
import select
import getopt
import threading

import cerebrum_path
import cereconf

from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from job_utils import *

debug_time = 0        # increase time by N seconds every second
max_sleep = 300
current_time = time.time()
db = Factory.get('Database')()

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")
ExitProgram = 'ExitProgram'

class JobRunner(object):
    def __init__(self, scheduled_jobs):
        self.scheduled_jobs = scheduled_jobs
        self.runner_cw = threading.Condition()
        self.db_qh = DbQueueHandler(db, logger)
        self.all_jobs = {}
        self.sleep_to = None
        
    def reload_scheduled_jobs(self):
        reload(self.scheduled_jobs)
        # The old all_jobs dict may contain information that we want
        # to preserve, such as pid
        new_jobs = self.scheduled_jobs.get_jobs()
        for job in self.all_jobs.keys():
            if not new_jobs.has_key(job):
                # TBD: Should we do something if the job is running?
                del(self.all_jobs[job])
        for job in new_jobs.keys():
            if self.all_jobs.has_key(job):     # Replacing an existing job with same name
                new_jobs[job].copy_runtime_params(self.all_jobs[job])
                self.all_jobs[job] = new_jobs[job]
            else:
                self.all_jobs[job] = new_jobs[job]
                if self.all_jobs[job].call is not None:
                    self.all_jobs[job].call.set_id(job)
                    self.all_jobs[job].call.set_logger(logger)
        # Also check if last_run values has been changed in the DB (we
        # don't bother with locking the update to the dict)
        self.last_run = self.db_qh.get_last_run()

    def insert_job(self, job):
        """Recursively add jobb and all its prerequisited jobs.

        We allways process all parents jobs, but they are only added to
        the ready_to_run queue if it won't violate max_freq."""

        if self.all_jobs[job].pre is not None:
            for j in self.all_jobs[job].pre:
                self.insert_job(j)

        if job not in self.ready_to_run or self.all_jobs[job].multi_ok:
            if (self.all_jobs[job].max_freq is None
                or current_time - self.last_run.get(job, 0) > self.all_jobs[job].max_freq):
                self.ready_to_run.append(job)

        if self.all_jobs[job].post is not None:
            for j in self.all_jobs[job].post:
                self.insert_job(j)

    def find_ready_jobs(self, jobs):
        """Populates the ready_to_run queue with jobs.  Returns number of
        seconds to next event (if positive, ready_to_run will be empty)"""
        global current_time
        if debug_time:
            current_time += debug_time
        else:
            current_time = time.time()
        min_delta = 999999
        for k in jobs.keys():
            delta = current_time - self.last_run.get(k, 0)
            if jobs[k].when is not None:
                n = jobs[k].when.next_delta(self.last_run.get(k, 0), current_time)
                if n <= 0:
                    pre_len = len(self.ready_to_run)
                    self.insert_job(k)
                    # If max_freq or similar prevented a run, don't return a small delta
                    if pre_len == len(self.ready_to_run):
                        n = min_delta
                min_delta = min(n, min_delta)
        return min_delta

    def handle_completed_jobs(self, running_jobs):
        """Handle any completed jobs (only jobs that has
        call != None).  Will block if any of the jobs has wait=1"""
        for tmp_job in running_jobs:
            ret = self.all_jobs[tmp_job].call.cond_wait()
            logger.debug("cond_wait(%s) = %s" % (tmp_job, ret))
            if ret is None:          # Job not completed
                pass
            else:
                if isinstance(ret, tuple):
                    if os.WIFEXITED(ret[0]):
                        msg = "exit_code=%i" % os.WEXITSTATUS(ret[0])
                    else:
                        msg = "exit_status=%i" % ret[0]
                    logger.error("%s for %s, check %s" % (msg, tmp_job, ret[1]))
                running_jobs.remove(tmp_job)
                if debug_time:
                    self.last_run[tmp_job] = current_time
                else:
                    self.last_run[tmp_job] = time.time()
                self.db_qh.update_last_run(tmp_job, self.last_run[tmp_job])

    def wake_runner(self):
        logger.debug("Waking up")
        self.runner_cw.acquire()
        self.runner_cw.notify()
        self.runner_cw.release()
        if hasattr(self, 'timer_wait'):
            self.timer_wait.cancel()

    # There is a python supplied sched module, but we don't use it for now...
    def runner(self):
        self.reload_scheduled_jobs()
        self.ready_to_run = []
        running_jobs = []
        prev_loop_time = 0
        n_fast_loops = 0
        while True:
            if time.time() - prev_loop_time < 2:
                logger.debug("Fast loop: %s" % (time.time() - prev_loop_time))
                n_fast_loops += 1
                # Allow a moderatly high number of fast loops as
                # AssertRunning jobs may finish very quickly
                if n_fast_loops > 20:
                    logger.critical("Looping too fast.. must be a bug, aborting!")
                    break
            else:
                n_fast_loops = 0
            prev_loop_time = time.time()
            for job in self.ready_to_run:
                if job == 'quit':
                    raise ExitProgram
                self.handle_completed_jobs(running_jobs)
                # Start the job
                if self.all_jobs[job].call is not None:
                    if self.all_jobs[job].call.setup():
                        logger.debug("Executing %s" % job)
                        self.all_jobs[job].call.execute()
                        running_jobs.append(job)
                self.handle_completed_jobs(running_jobs)

                # For jobs that has call = None, last_run will be set
                # after all pre-jobs with wait=1 has completed.  For
                # jobs with wait=0 we update last_run immeadeately to
                # prevent find_ready_jobs from trying to start it on
                # next loop.
                if (self.all_jobs[job].call is None or
                    self.all_jobs[job].call.wait == 0):
                    if debug_time:
                        self.last_run[job] = current_time
                    else:
                        self.last_run[job] = time.time()
                    self.db_qh.update_last_run(job, self.last_run[job])

            # figure out what jobs to run next
            self.ready_to_run = []
            logger.debug("Finding ready jobs (running: %s)" % str(running_jobs))
            delta = self.find_ready_jobs(self.all_jobs)
            logger.debug("%s New queue (delta=%s): %s" % (
                "-" * 20, delta, ", ".join(self.ready_to_run)))
            if delta > 0:
                if debug_time:
                    time.sleep(1)
                else:
                    pre_time = time.time()
                    # Sleep until next job, either Timer or
                    # SocketHandling will wake us
                    self.sleep_to = pre_time + min(max_sleep, delta)
                    self.runner_cw.acquire()
                    # We have the lock.  Set up the wake-up call for
                    # ourselves (but don't release the lock until the
                    # timer has been activated, as we won't hear it if
                    # it goes off before we're wait()ing).
                    self.timer_wait = threading.Timer(min(max_sleep, delta),
                                                      self.wake_runner)
                    self.timer_wait.setDaemon(True)
                    self.timer_wait.start()
                    # Now, release the lock and wait for the timer to
                    # wake us.
                    self.runner_cw.wait()
                    self.sleep_to = None
                    # We're awake, and don't need the lock anymore.
                    self.runner_cw.release()
                    if time.time() - pre_time < min(max_sleep, delta):
                        # Work-around for some machines that don't
                        # sleep long enough
                        time.sleep(1)

def usage(exitcode=0):
    print """job_runner.py --reload | --config file | --quit | --status"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['reload', 'quit', 'status', 'config='])
    except getopt.GetoptError:
        usage(1)
    #global scheduled_jobs
    alt_config = False
    for opt, val in opts:
        if opt in('--reload', '--quit', '--status'):
            if opt == '--reload':
                cmd = 'RELOAD'
            elif opt == '--quit':
                cmd = 'QUIT'
            elif opt == '--status':
                cmd = 'STATUS'
            sock = SocketHandling()
            try:
                print "Response: %s" % sock.send_cmd(cmd)
            except SocketHandling.Timeout:
                print "Timout contacting server, is it running?"
            sys.exit(0)
        elif opt in ('--config',):
            sys.path.insert(0, val[:val.rindex("/")])
            name = val[val.rindex("/")+1:]
            name = name[:name.rindex(".")]
            exec("import %s as tmp" % name)
            scheduled_jobs = tmp
            # sys.path = sys.path[1:] #With this reload(module) loads another file(!)
            alt_config = True
    if not alt_config:
        import scheduled_jobs
    sock = SocketHandling()
    if(sock.ping_server()):
        print "Server already running"
        sys.exit(1)
    jr = JobRunner(scheduled_jobs)
    jr_thread = threading.Thread(target=sock.start_listener, args=(jr,))
    jr_thread.setDaemon(True)
    jr_thread.start()
    try:
        jr.runner()
    except ExitProgram:
        logger.debug("Terminated by Quit")
    logger.debug("bye")

if __name__ == '__main__':
    main()
