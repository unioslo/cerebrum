#!/usr/bin/env python2.2

# $Id$
# TBD: Paralellitet: dersom det er flere jobber i ready_to_run køen
# som ikke har noen ukjørte pre-requisites, kan de startes samtidig.

"""job_runner is a scheduler that runs specific commands at certain
times.  Each command is represended by an Action class that may have
information about when and how often a job should be ran, as well as
information about jobs that should be ran before or after itself; see
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
- running multiple jobs in paralell, in particular manually added jobs
  should normally start imeadeately
"""

import time
import os
import sys
import popen2
import fcntl
import select
import getopt
import thread

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
#Timeout = 'Timeout'
class JobRunner(object):
    def __init__(self, scheduled_jobs):
        self.scheduled_jobs = scheduled_jobs

    def reload_scheduled_jobs(self):
        reload(self.scheduled_jobs)
        self.all_jobs = self.scheduled_jobs.get_jobs()
        for job in self.all_jobs.keys():
            if self.all_jobs[job].call is not None:
                self.all_jobs[job].call.set_id(job)
                self.all_jobs[job].call.set_logger(logger)

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
                    self.insert_job(k)
                min_delta = min(n, min_delta)
        return min_delta

    def handle_completed_jobs(self, db_qh, running_jobs):
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
                db_qh.update_last_run(tmp_job, self.last_run[tmp_job])

    # There is a python supplied sched module, but we don't use it for now...
    def runner(self):
        self.reload_scheduled_jobs()
        self.ready_to_run = []
        db_qh = DbQueueHandler(db, logger)
        self.last_run = db_qh.get_last_run()
        running_jobs = []
        prev_loop_time = 0
        n_fast_loops = 0
        while 1:
            if time.time() - prev_loop_time < 2:
                logger.debug("Fast loop: %s" % (time.time() - prev_loop_time))
                n_fast_loops += 1
                if n_fast_loops > 3:
                    logger.critical("Looping too fast.. must be a bug, aborting!")
                    break
            else:
                n_fast_loops = 0
            prev_loop_time = time.time()
            for job in self.ready_to_run:
                self.handle_completed_jobs(db_qh, running_jobs)
                # Start the job
                if self.all_jobs[job].call is not None:
                    if self.all_jobs[job].call.setup():
                        logger.debug("Executing %s" % job)
                        self.all_jobs[job].call.execute()
                        running_jobs.append(job)
                self.handle_completed_jobs(db_qh, running_jobs)

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
                    db_qh.update_last_run(job, self.last_run[job])

            # figure out what jobs to run next
            self.ready_to_run = []
            logger.debug("Finding ready jobs (running: %s)" % str(running_jobs))
            delta = self.find_ready_jobs(self.all_jobs)
            logger.debug("%s New queue (delta=%s): %s" % (
                "-" * 20, delta, ", ".join(self.ready_to_run)))
            if(delta > 0):
                if debug_time:
                    time.sleep(1)
                else:
                    pre_time = time.time()
                    time.sleep(min(max_sleep, delta))      # sleep until next job
                    if time.time() - pre_time < min(max_sleep, delta):
                        # Work-around for some machines that don't sleep long enough
                        time.sleep(1)

def usage(exitcode=0):
    print """job_runner.py --reload | --config file"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['reload', 'config='])
    except getopt.GetoptError:
        usage(1)
    #global scheduled_jobs
    alt_config = False
    for opt, val in opts:
        if opt == '--reload':
            sock = SocketHandling()
            try:
                print "Response: %s" % sock.send_cmd("RELOAD")
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
    thread.start_new(sock.start_listener, (jr,))
    jr.runner()

if __name__ == '__main__':
    main()
