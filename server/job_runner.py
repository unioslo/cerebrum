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
            # print "  %d for %s / %s" % (delta, k, jobs[k].when)
            if jobs[k].when is not None:
                n = jobs[k].when.next_delta(self.last_run.get(k, 0), current_time)
                if n <= 0:
                    self.insert_job(k)
                min_delta = min(n, min_delta)
        return min_delta

    # There is a python supplied sched module, but we don't use it for now...
    def runner(self):
        self.reload_scheduled_jobs()
        self.ready_to_run = []
        db_qh = DbQueueHandler(db, logger)
        self.last_run = db_qh.get_last_run()
        while 1:
            for job in self.ready_to_run:
                if self.all_jobs[job].call is not None:
                    self.all_jobs[job].call.setup()
                    self.all_jobs[job].call.execute()
                    self.all_jobs[job].call.cleanup()
                if debug_time:
                    self.last_run[job] = current_time
                else:
                    self.last_run[job] = time.time()
                db_qh.update_last_run(job, self.last_run[job])
            # figure out what jobs to run next
            self.ready_to_run = []
            delta = self.find_ready_jobs(self.all_jobs)
            logger.debug("New queue (delta=%s): %s" % (delta, ", ".join(self.ready_to_run)))
            if(delta > 0):
                if debug_time:
                    time.sleep(1)
                else:
                    time.sleep(min(max_sleep, delta))      # sleep until next job

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
