#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# $Id$
import popen2
import fcntl
import os
import select
import sys
import time
import random

import cereconf

LockExists = 'LockExists'

debug_dryrun = False  # Debug only: execs "/bin/sleep 2", and not the job
if debug_dryrun:
    random.seed()

class Action(object):
    def __init__(self, pre=None, post=None, call=None, max_freq=None, when=None,
                 multi_ok=0):
        # TBD: Trenger vi engentlig post?  Dersom man setter en jobb
        # til å kjøre 1 sek etter en annen vil den automatisk havne
        # bakerst i ready_to_run køen, og man oppnår dermed det samme.
        # Vil dog kun funke for jobber som kjører på bestemte
        # tidspunkt.

        # TBD: extra parameter 'lock'?  Would lock the job with this
        # name for the indicated number of seconds (emitting warning
        # if lock has expired, requiring manual intervention)

        """
        - pre contains name of jobs that must run before this job.
        - post contains name of jobs that must run after this job.
        - call contains the command to call to run the command
        - max_freq indicates how often (in seconds) the job may run
        - when indicates when the job should be ran.  None indicates
          that the job should not run directly (normally ran as a
          prerequisite for another job).
        - multi_ok indicates if multiple instances of this job may
          appear in the ready_to_run queue

          If max_freq is None, the job will allways run.  If when is
          None, the job will only run if it is a prerequisite of
          another job."""

        self.pre = pre or []
        self.call = call
        self.max_freq = max_freq
        self.when = when
        self.post = post or []
        self.multi_ok = multi_ok

    def copy_runtime_params(self, other):
        """When reloading the configuration, we must preserve some
        runtime params when we alter the all_jobs dict"""
        if self.call is not None and other.call is not None:
            self.call.copy_runtime_params(other.call)

class CallableAction(object):
    """Abstract class representing the call parameter to Action"""

    def __init__(self):
        self.id = None
        self.wait = 1
        
    def setup(self):
        """Must return 1 if it is OK to run job now.  As it may be
        perfectly OK to return 0, the framework issues no warning
        based on the return value."""
        return 1

    def execute(self):
        raise RuntimeError, "Override CallableAction.execute"

    def cond_wait(self):
        """Check if process has completed, and report any errors.
        Clean up temporary files for the completed job.

        If self.wait=1, this operation is blocking.

        Returns:
        - None: job has not completed
        - 1: Job completed successfully
        - (exitcode, dirname_for_output_files): on error"""
        pass

    def set_id(self, id):
        self.id = id
        self.locfile_name = "%s/job-runner-%s.lock" % (cereconf.JOB_RUNNER_LOG_DIR, id)

    def set_logger(self, logger):
        self.logger = logger

    def check_lockfile(self):
        """Flag an error iff the process whos pid is in the lockfile
        is running."""
        if os.path.isfile(self.locfile_name):
            f = open(self.locfile_name, 'r')
            pid = f.readline()
            if(pid.isdigit()):
                try:
                    os.kill(int(pid), 0)
                    raise LockExists
                except OSError:
                    pass   # Process doesn't exist

    def make_lockfile(self):
        f=open(self.locfile_name, 'w')
        f.write("%s" % os.getpid())
        f.close()

    def copy_runtime_params(self, other):
        self.logger = other.logger
        self.id = other.id
        self.locfile_name = other.locfile_name
        
class System(CallableAction):
    def __init__(self, cmd, params=[], stdout_ok=0):
        super(System, self).__init__()
        self.cmd = cmd
        self.params = list(params)
        self.stdout_ok = stdout_ok
        self.run_dir = None

    def setup(self):
        self.logger.debug("Setup: %s" % self.id)
        try:
            self.check_lockfile()
        except LockExists:
            self.logger.error("Lockfile exists, this is unexpected!")
            return 0
        return 1
        
    def execute(self):
        self.logger.debug2("Execute %s (%s, args=%s)" % (
            self.id, self.cmd, str(self.params)))
        self.run_dir = "%s/%s" % (cereconf.JOB_RUNNER_LOG_DIR, self.id)
        child_pid = os.fork()
        if child_pid:
            self.logger.debug2("child: %i (p=%i)" % (child_pid, os.getpid()))
            return child_pid
        self.make_lockfile()
        self.logger.debug("Entering %s" % self.run_dir)
        if not os.path.exists(self.run_dir):
            os.mkdir(self.run_dir)
        os.chdir(self.run_dir)

        #saveout = sys.stdout
        #saveerr = sys.stderr
        new_stdout = open("stdout.log", 'a', 0)
        new_stderr = open("stderr.log", 'a', 0)
        os.dup2(new_stdout.fileno(), sys.stdout.fileno())
        os.dup2(new_stderr.fileno(), sys.stderr.fileno())
        try:
            p = self.params[:]
            p.insert(0, self.cmd)
            if debug_dryrun:
                os.execv("/bin/sleep", [self.id, str(5+random.randint(5,10))])
            os.execv(self.cmd, p)
        except OSError, e:
            sys.exit(e.errno)
        logger.error("OOPS!  This code should never be reached")
        sys.exit(1)

    def cond_wait(self, child_pid):
        pid, exit_code = os.waitpid(child_pid, os.WNOHANG)
        self.logger.debug2("Wait (wait=%i) ret: %s/%s" % (
            self.wait, pid, exit_code))
        if pid == child_pid:
            if ((self.stdout_ok == 0 and 
                 os.path.getsize("%s/stdout.log" % self.run_dir) > 0) or 
                os.path.getsize("%s/stderr.log" % self.run_dir) > 0 or
                exit_code != 0):
                newdir = "%s.%s" % (self.run_dir, time.time())
                os.rename(self.run_dir, newdir)
                return (exit_code, newdir)
            self._cleanup()        
            return 1
        else:
            self.logger.debug2("Wait returned %s/%s" % (pid, exit_code))
        return None

    def _cleanup(self):
        os.unlink(self.locfile_name)
        os.unlink("%s/stdout.log" % self.run_dir)
        os.unlink("%s/stderr.log" % self.run_dir)

    def copy_runtime_params(self, other):
        super(System, self).copy_runtime_params(other)
        self.run_dir = other.run_dir

class AssertRunning(System):
    def __init__(self, cmd, params=[], stdout_ok=0):
        super(AssertRunning, self).__init__(cmd, params, stdout_ok)
        self.wait = 0

    def setup(self):
        self.logger.debug("setup %s" % self.id)
        try:
            self.check_lockfile()
        except LockExists:
            self.logger.debug("%s already running" % self.id)
            return 0
        return 1
