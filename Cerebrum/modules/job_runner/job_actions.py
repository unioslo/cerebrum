# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

# $Id$
import fcntl
import os
import select
import sys
import time
import random
import inspect

import cerebrum_path
import cereconf

LockExists = 'LockExists'

debug_dryrun = False  # Debug only: execs "/bin/sleep 2", and not the job
if debug_dryrun:
    random.seed()

class Action(object):
    def __init__(self, pre=None, post=None, call=None, max_freq=None, when=None,
                 notwhen=None, max_duration=2*60*60, multi_ok=0, nonconcurrent=[]):
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
        - max_freq indicates how often (in seconds) the job may run,
          or in other words, for how long the previous result will be
          reused.  Set it to None to always run.
        - max_duration indicates how long (in seconds) the job should
          be allowed to run before giving up and killing it.  Default
          is 2 hours.  Set it to None to disable.
        - when indicates when the job should be run.  None indicates
          that the job should not run directly (normally run as a
          prerequisite for another job).
        - notwhen indicates when a job should not be started.  Jobs
          which are running when the notwhen interval arrives are
          allowed to complete normally.
        - multi_ok indicates if multiple instances of this job may
          appear in the ready_to_run queue
        - nonconcurrent contains the names of jobs that if running,
          should postpone the start of this job till they are (all)
          finished.

        """
        self.pre = pre or []
        self.call = call
        self.max_freq = max_freq
        self.max_duration = max_duration
        self.when = when
        self.post = post or []
        self.multi_ok = multi_ok
        self.last_exit_msg = None
        self.notwhen = notwhen
        self.nonconcurrent = nonconcurrent

    def copy_runtime_params(self, other):
        """When reloading the configuration, we must preserve some
        runtime params when we alter the all_jobs dict"""
        if self.call is not None and other.call is not None:
            self.call.copy_runtime_params(other.call)

    def get_pretty_cmd(self):
        if not self.call:
            return None

        # We want to have pretty callable parameters
        arguments = list()
        for p in self.call.params:
            if callable(p):
                try:
                    arguments.append(inspect.getsource(p))
                except IOError:
                    arguments.append(str(p))
            else:
                arguments.append(str(p))
        return "%s %s" % (self.call.cmd, " ".join(arguments))

    def next_delta(self, last_run, current_time):
        """Return estimated number of seconds to next time the Action
        is allowed to run.  Jobs should only be ran if the returned
        value is negative."""
        
        delta = current_time - last_run
        if self.when is not None:
            if self.notwhen is not None:
                leave_at = self.notwhen.time.delta_to_leave(current_time)
                if leave_at > 0:
                    return leave_at
            n = self.when.next_delta(last_run, current_time)
            return n

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
        self.lockfile_name = "%s/job-runner-%s.lock" % (cereconf.JOB_RUNNER_LOG_DIR, id)

    def set_logger(self, logger):
        self.logger = logger

    def check_lockfile(self):
        """Flag an error iff the process whos pid is in the lockfile
        is running."""
        if os.path.isfile(self.lockfile_name):
            f = open(self.lockfile_name, 'r')
            pid = f.readline()
            if(pid.isdigit()):
                try:
                    os.kill(int(pid), 0)
                    raise LockExists
                except OSError:
                    pass   # Process doesn't exist

    def make_lockfile(self):
        f=open(self.lockfile_name, 'w')
        f.write("%s" % os.getpid())
        f.close()

    def free_lock(self):
        os.unlink(self.lockfile_name)
        
    def copy_runtime_params(self, other):
        self.logger = other.logger
        self.id = other.id
        self.lockfile_name = other.lockfile_name
        
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
            self.logger.error("%s: Lockfile exists, this is unexpected!" %
                              self.lockfile_name)
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
        try:
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
                p = list()
                for argument in self.params[:]:
                    if callable(argument):
                        argument = argument()
                    else:
                        argument = str(argument)
                    p.append(argument)

                p.insert(0, self.cmd)
                if debug_dryrun:
                    os.execv("/bin/sleep", [self.id, str(5+random.randint(5,10))])
                os.execv(self.cmd, p)
            except OSError, e:
                self.logger.debug("Exec failed, check the command that was executed.")
                # avoid cleanup handlers, seems to mess with logging
                sys.exit(e.errno)
        except SystemExit:
            #self.logger.debug("not trapping exit")
            raise   # Don't stop the above sys.exit()
        except:
            # Full disk etc. can trigger this
            self.logger.critical("Caught unexpected exception", exc_info=1)
        self.logger.error("OOPS!  This code should never be reached")
        sys.exit(1)

    def cond_wait(self, child_pid):
        # May raise OSError: [Errno 4]: Interrupted system call
        pid, exit_code = os.waitpid(child_pid, os.WNOHANG)
        self.logger.debug2("Wait (wait=%i) ret: %s/%s" % (
            self.wait, pid, exit_code))
        if pid == child_pid:
            if not (os.path.exists(self.run_dir) and
                    os.path.exists("%s/stdout.log" % self.run_dir) and
                    os.path.exists("%s/stderr.log" % self.run_dir)):
                # May happen if the exec failes due to full-disk etc.
                if not exit_code:
                    self.logger.warn(
                        "exit_code=0, and %s don't exist!" % self.run_dir)
                self.last_exit_msg = "exit_code=%i, full disk?" % exit_code
                return (exit_code, None)
            if (exit_code != 0 or
                (self.stdout_ok == 0 and 
                 os.path.getsize("%s/stdout.log" % self.run_dir) > 0) or 
                os.path.getsize("%s/stderr.log" % self.run_dir) > 0):
                newdir = "%s.%s" % (self.run_dir, time.time())
                os.rename(self.run_dir, newdir)
                self.last_exit_msg = "exit_code=%i, check %s" % (exit_code, newdir)
                return (exit_code, newdir)
            self.last_exit_msg = "Ok"
            self._cleanup()        
            return 1
        else:
            self.logger.debug2("Wait returned %s/%s" % (pid, exit_code))
        return None

    def _cleanup(self):
        self.free_lock()
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

    

class UniqueActionAttrs(type):
    """Prevent two different classes from defining an Action with the
    same name (is there an easy way to also detect it in the same class?)."""
    
    def __new__(cls, name, bases, dict_):
        known = dict([(k, name) for k, v in dict_.items()
                      if isinstance(v, Action)])
        for base in bases:
            for k in dir(base):
                if isinstance(getattr(base, k), Action):
                    if k in known:
                        raise ValueError, "%s.%s already defined in %s" % (
                            base.__name__, k, known[k])
                    known[k] = base.__name__
        return type.__new__(cls,name, bases, dict_)



class Jobs(object):
    """
    Utility class meant for grouping related job-actions
    together. Contains logic for checking uniqueness and non-cyclicity
    in job definitions.
    
    """
    __metaclass__ = UniqueActionAttrs
    
    def validate(self):
        all_jobs = self.get_jobs(_from_validate=True)
        keys = all_jobs.keys()
        keys.sort()
        for name, job in all_jobs.items():
            for n in job.pre:
                if not all_jobs.has_key(n):
                    raise ValueError, "Undefined pre-job '%s' in '%s'" % (
                        n, name)
            for n in job.post:
                if not all_jobs.has_key(n):
                    raise ValueError, "Undefined post-job '%s' in '%s'" % (
                        n, name)


    def check_cycles(self, joblist):
        """Check whether job prerequisites make a cycle."""
        
        class node:
            UNMARKED = 0
            INPROGRESS = 1
            DONE = 2
        
            def __init__(self, key, pre, post):
                self.key = key
                self.pre = pre
                self.post = post
                self.mark = self.UNMARKED
                

        # construct a graph (bunch of interlinked nodes + a dict to
        # access them)
        graph = dict()
        for name, job in joblist.iteritems():
            x = node(name, job.pre, job.post)
            graph[name] = x

        # remap names to object (it'll be easier later)
        for n in graph.itervalues():
            n.pre = [graph[key] for key in n.pre]
            n.post = [graph[key] for key in n.post]

        # scan all graph nodes and try to find cycles.
        for n in graph.itervalues():
            tmp = self.find_cycle(n)
            if tmp:
                raise ValueError, ("joblist has a cycle: %s" % 
                                   [x.key for x in tmp])


    def find_cycle(self, node):
        """Locate a cycle in which node is a part.
        
        This is a standard depth-first search. Nothing fancy.

        The method returns None when node has no cycles or a list containing
        whatever of the cycle we've collected in the recursive calls.
        """

        # If we know there are no cycles from this node, we are done
        if node.mark == node.DONE:
            return None

        # Yay! a cycle
        if node.mark == node.INPROGRESS:
            # we collect the entire recursion stack on the way out to
            # report the cycle back to the user
            return [node]

        # The usual case: we start with a new node.
        node.mark = node.INPROGRESS
        for successor in node.pre:
            tmp = self.find_cycle(successor)
            if tmp:
                tmp.append(node)
                return tmp

        # if we are here, there were no cycles in which *this* node
        # participates and we are done.
        node.mark = node.DONE
        return None


    def get_jobs(self, _from_validate=False):
        """Returns a dictionary with all actions, where the keys are
        the names of the actions and the correspondingvalues are the
        actions themselves.

        If '_from_validate' is True, this method will also call
        'validate' before putting the dictionary together, as well as
        check that there are no cyclic dependencies in the
        pre-/post-definitions of jobs.

        """
        if not _from_validate:
            self.validate()
        ret = {}
        for n in dir(self):
            c = getattr(self, n)
            if isinstance(c, Action):
                ret[n] = c
                
        if not _from_validate:
            self.check_cycles(ret)
            
        return ret

def _test_time():
    from Cerebrum.modules.job_runner.job_utils import When, Time
    ac =  Action(call = System("echo yes"),
                 max_freq = 5*60,
                 when = When(freq = 5*60),
                 notwhen = When(time=Time(hour=[4])))
    last_run = time.mktime(time.strptime('2005-3:58', '%Y-%H:%M'))
    print ac.next_delta(last_run,
                        last_run + 60*8)
    print ac.next_delta(last_run,
                        last_run + 60*60)
    print ac.next_delta(last_run,
                        last_run + 60*65)

if __name__ == '__main__':
    _test_time()

