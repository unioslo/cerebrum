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
import signal
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
from Cerebrum.modules.job_runner.job_utils import SocketHandling, JobQueue

debug_time = 0        # increase time by N seconds every second
max_sleep = 300
noia_sleep_seconds = 310  # trap missing SIGCHLD (known race-condition,
                          # see comment in run_job_loop)
current_time = time.time()
db = Factory.get('Database')()

logger = Factory.get_logger("cronjob")
runner_cw = threading.Condition()

use_thread_lock = False  # don't seem to work

if True:
    # useful for debugging, and to work-around a wierd case where the
    # logger would hang
    ppid = os.getpid()
    class MyLogger(object):
        def __init__(self):
            self.last_msg = time.time()
            
        def show_msg(self, lvl, msg):
            delta = int(time.time() - self.last_msg)
            self.last_msg = time.time()
            lvl = "%3i %s" % (delta, lvl)
            if os.getpid() != ppid:
                lvl = "      %s" % lvl
            sys.stdout.write("%s [%i] %s\n" % (lvl, os.getpid(), msg))
            sys.stdout.flush()

        def debug2(self, msg):
            self.show_msg("DEBUG2", msg)
            pass
        
        def debug(self, msg):
            self.show_msg("DEBUG", msg)

        def error(self, msg):
            self.show_msg("ERROR", msg)

        def fatal(self, msg):
            self.show_msg("FATAL", msg)

    logger = MyLogger()

def sigchld_handler(signum, frame):
    """Sigchild-handler that wakes the main-thread when a child exits"""
    logger.debug2("sigchld_handler(%s)" % (str(signum)))
    signal.signal(signal.SIGCHLD, sigchld_handler)
signal.signal(signal.SIGCHLD, sigchld_handler)

class JobRunner(object):
    def __init__(self, scheduled_jobs):
        self.my_pid = os.getpid()
        self.timer_wait = None
        signal.signal(signal.SIGUSR1, JobRunner.sig_general_handler)
        self.job_queue = JobQueue(scheduled_jobs, db, logger)
        self._should_quit = False
        self.sleep_to = None

    def sig_general_handler(signum, frame):
        """General signal handler, for places where we use signal.pause()"""
        logger.debug2("siggeneral_handler(%s)" % (str(signum)))
    sig_general_handler = staticmethod(sig_general_handler)

    def signal_sleep(self, seconds):
        # SIGALRM is already used by the SocketThread, se we arrange
        # for a SIGUSR1 to be delivered instead
        runner_cw.acquire()
        if not self.timer_wait:  # Only have one signal-sleep thread
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
                    logger.debug("error (%s): %s" % (job['name'], msg))
                time.sleep(1)
                continue
            logger.debug2("cond_wait(%s) = %s" % (job['name'], ret))
            if ret is None:          # Job not completed
                pass
            else:
                did_wait = True
                if isinstance(ret, tuple):
                    if os.WIFEXITED(ret[0]):
                        msg = "exit_code=%i" % os.WEXITSTATUS(ret[0])
                    else:
                        msg = "exit_status=%i" % ret[0]
                    logger.error("%s for %s, check %s" % (msg, job['name'], ret[1]))
                self.job_queue.job_done(job['name'], job['pid'])
        return did_wait

    def wake_runner_signal(self):
        logger.debug("Waking up")
        os.kill(self.my_pid, signal.SIGUSR1)

    def quit(self):
        self._should_quit = True
        self.wake_runner_signal()

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
            logger.debug("Queue: %s" % self.job_queue.get_run_queue())
            tmp_queue = self.job_queue.get_run_queue()[:]   # loop modifies list
            completed_nowait_job = False
            for job_name in tmp_queue:
                job_ref = self.job_queue.get_known_job(job_name)
                if (job_ref.call and job_ref.call.wait and
                    num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                    # This is a minor optimalization that may be
                    # skipped.  Hopefully it makes the log easier to
                    # read
                    continue
                if self.job_queue.has_queued_prerequisite(job_name):
                    logger.debug2("has queued prereq: %s" % job_name)
                    continue
                logger.debug2("  ready: %s" % job_name)
                
                if job_ref.call is not None:
                    logger.debug("  exec: %s, # running_jobs=%i" % (
                        job_name, len(self.job_queue.get_running_jobs())))
                    if (job_ref.call.wait and
                        num_running >= cereconf.JOB_RUNNER_MAX_PARALELL_JOBS):
                        logger.debug("  too many paralell jobs (%s/%i)" % (
                            job_name, num_running))
                        continue
                    if job_ref.call.setup():
                        child_pid = job_ref.call.execute()
                        self.job_queue.job_started(job_name, child_pid)
                        if job_ref.call.wait:
                            num_running += 1
                # Mark jobs that we should not wait for as completed
                if (job_ref.call is None or not job_ref.call.wait):
                    self.job_queue.job_done(job_name, None)
                    completed_nowait_job = True

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
            signal.pause() # continue on SIGCHLD/SIGALRM.  Won't hurt if we
                           # get another signal
            runner_cw.acquire()
            self.timer_wait.cancel()
            self.timer_wait = None
            runner_cw.release()
            logger.debug("resumed")
    
def usage(exitcode=0):
    print """job_runner.py [options]:
      --reload: re-read the config file
      --config file : use alternative config-file
      --quit : exit gracefully (allowing current job to complete)
      --status : show status for a running job-runner
      --dump level : shows dependency graph, level must be in the range 0-3"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['reload', 'quit', 'status', 'config=',
                                    'dump='])
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
            if val.find("/") == -1:
                sys.path.insert(0, '.')
                name = val
            else:
                sys.path.insert(0, val[:val.rindex("/")])
                name = val[val.rindex("/")+1:]
            name = name[:name.rindex(".")]
            exec("import %s as tmp" % name)
            scheduled_jobs = tmp
            # sys.path = sys.path[1:] #With this reload(module) loads another file(!)
            alt_config = True
        elif opt in ('--dump',):
            JobQueue.dump_jobs(scheduled_jobs, int(val))
            sys.exit(0)
    if not alt_config:
        import scheduled_jobs
    sock = SocketHandling()
    if(sock.ping_server()):
        print "Server already running"
        sys.exit(1)
    jr = JobRunner(scheduled_jobs)
    if True:
        socket_thread = threading.Thread(target=sock.start_listener, args=(jr,))
        socket_thread.setDaemon(True)
        socket_thread.setName("socket_thread")
        socket_thread.start()

    jr.run_job_loop()
    logger.debug("bye")

if __name__ == '__main__':
    main()
