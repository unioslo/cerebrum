# -*- coding: utf-8 -*-
#
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
""" Job runner job types. """

import inspect
import io
import os
import random
import sys
import time

from six import text_type
from six.moves import shlex_quote as quote

import cereconf


class LockExists(Exception):
    """ An exception to throw if unable to acquire job lock. """

    def __init__(self, lock_pid):
        self.acquire_pid = os.getpid()
        self.lock_pid = lock_pid
        super(LockExists, self).__init__("locked by pid=%d" % lock_pid)


debug_dryrun = False  # Debug only: execs "/bin/sleep 2", and not the job

if debug_dryrun:
    random.seed()


class Action(object):

    def __init__(self,
                 pre=None,
                 post=None,
                 call=None,
                 max_freq=None,
                 when=None,
                 notwhen=None,
                 max_duration=4*60*60,
                 multi_ok=0,
                 nonconcurrent=[]):
        """
        :param list pre:
            List of names (strings) of jobs that must run before this job.
        :param list post:
            List of names (strings) of jobs that must run after this job.
        :param CallableAction call:
            A command to call in order to run the job.
        :param int max_freq:
            max_freq indicates how often (in seconds) the job may run, or in
            other words, for how long the previous result will be reused.  Set
            it to None to always run.
        :param int max_duration:
            max_duration indicates how long (in seconds) the job should be
            allowed to run before giving up and killing it.  Default is
            2 hours.  Set it to None to disable.
        :param times.When when:
            when indicates when the job should be run.  None indicates that the
            job should not run directly (normally run as a prerequisite for
            another job).
        :param TODO notwhen:
            notwhen indicates when a job should not be started.  Jobs which are
            running when the notwhen interval arrives are allowed to complete
            normally.
        :param bool multi_ok:
            multi_ok indicates if multiple instances of this job may appear in
            the ready_to_run queue
        :param TODO nonconcurrent:
            nonconcurrent contains the names of jobs that if running, should

        """

        # TBD: Trenger vi engentlig post?  Dersom man setter en jobb
        # til å kjøre 1 sek etter en annen vil den automatisk havne
        # bakerst i ready_to_run køen, og man oppnår dermed det samme.
        # Vil dog kun funke for jobber som kjører på bestemte
        # tidspunkt.

        # TBD: extra parameter 'lock'?  Would lock the job with this
        # name for the indicated number of seconds (emitting warning
        # if lock has expired, requiring manual intervention)
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
                    arguments.append(repr(p))
            else:
                arguments.append(quote(text_type(p)))
        return "%s %s" % (self.call.cmd, " ".join(arguments))

    def next_delta(self, last_run, current_time):
        """Return estimated number of seconds to next time the Action
        is allowed to run.  Jobs should only be ran if the returned
        value is negative."""
        if self.when is not None:
            if self.notwhen is not None:
                leave_at = self.notwhen.time.delta_to_leave(current_time)
                if leave_at > 0:
                    return leave_at
            n = self.when.next_delta(last_run, current_time)
            return n


class LockFile(object):

    lock_dir = cereconf.JOB_RUNNER_LOG_DIR
    pre = 'job-runner-'
    ext = '.lock'

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<LockFile name=%r>' % self.name

    @property
    def filename(self):
        return os.path.join(
            self.lock_dir,
            ''.join((self.pre, self.name, self.ext)))

    def read(self):
        with io.open(self.filename, 'r', encoding='ascii') as f:
            return f.read()

    def write(self, data):
        with io.open(self.filename, 'w', encoding='ascii') as f:
            f.write(data)

    def exists(self):
        return os.path.exists(self.filename)

    def acquire(self, create=True):
        if self.exists():
            try:
                pid = int(self.read().strip())
                # Check if PID exists?
                os.kill(pid, 0)
                raise LockExists(pid)
            except (ValueError, OSError):
                # No such process or invalid file contents
                pass

        if create:
            # Process does not exist
            self.write(u"%d" % os.getpid())

    def release(self):
        os.unlink(self.filename)


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
        raise NotImplementedError("Override CallableAction.execute")

    def cond_wait(self):
        """Check if process has completed, and report any errors.

        Clean up temporary files for the completed job.
        If self.wait=1, this operation is blocking.

        :return:
            - None: job has not completed
            - 1: Job completed successfully
            - (exitcode, dirname_for_output_files): on error
        """
        pass

    def set_id(self, id):
        self.id = id
        self.lockfile = LockFile(id)

    def set_logger(self, logger):
        self.logger = logger

    def copy_runtime_params(self, other):
        self.logger = other.logger
        self.id = other.id
        self.lockfile = LockFile(other.id)


class System(CallableAction):

    def __init__(self, cmd, params=[], stdout_ok=0):
        super(System, self).__init__()
        self.cmd = cmd
        self.params = list(params)
        self.stdout_ok = stdout_ok

    def setup(self):
        self.logger.info("Setup: %s", self.id)
        try:
            self.lockfile.acquire(create=False)
        except LockExists:
            self.logger.error("Lockfile exists (%s), this is unexpected!",
                              self.lockfile.filename)
            return 0
        return 1

    @property
    def run_dir(self):
        return os.path.join(cereconf.JOB_RUNNER_LOG_DIR, self.id)

    @property
    def stdout_file(self):
        return os.path.join(self.run_dir, 'stdout.log')

    @property
    def stderr_file(self):
        return os.path.join(self.run_dir, 'stderr.log')

    def execute(self):
        self.logger.debug("Execute %s (%s, args=%s)",
                          self.id, self.cmd, repr(self.params))
        child_pid = os.fork()
        if child_pid:
            self.logger.debug("child: %i (p=%i)", child_pid, os.getpid())
            return child_pid
        try:
            self.lockfile.acquire()
            self.logger.info("Entering %s", self.run_dir)
            if not os.path.exists(self.run_dir):
                os.mkdir(self.run_dir)
            os.chdir(self.run_dir)

            new_stdout = open(self.stdout_file, 'a', 0)
            new_stderr = open(self.stderr_file, 'a', 0)
            os.dup2(new_stdout.fileno(), sys.stdout.fileno())
            os.dup2(new_stderr.fileno(), sys.stderr.fileno())
            try:
                p = list()
                for argument in self.params[:]:
                    if callable(argument):
                        argument = text_type(argument())
                    else:
                        argument = text_type(argument)
                    p.append(argument)

                # TODO: Why not self.id? It's a better process name than e.g.
                # 'scp'
                p.insert(0, self.cmd)
                if debug_dryrun:
                    os.execv("/bin/sleep", [self.id,
                                            str(5 + random.randint(5, 10))])
                os.execv(self.cmd, p)
            except OSError as e:
                self.logger.info("Exec failed, check the command that was"
                                 " executed.")
                # avoid cleanup handlers, seems to mess with logging
                raise SystemExit(e.errno)
        except SystemExit:
            # Don't stop the above SystemExit
            raise
        except:
            # Full disk etc. can trigger this
            self.logger.critical("Caught unexpected exception", exc_info=1)
        self.logger.error("OOPS!  This code should never be reached")
        raise SystemExit(1)

    def cond_wait(self, child_pid):
        # May raise OSError: [Errno 4]: Interrupted system call
        pid, exit_code = os.waitpid(child_pid, os.WNOHANG)
        self.logger.debug("cond_wait(%r) id=%r, wait=%r, ret=%r",
                          child_pid, self.id, self.wait, (pid, exit_code))
        if pid == child_pid:
            if not all(os.path.exists(p) for p in (self.run_dir,
                                                   self.stdout_file,
                                                   self.stderr_file)):
                # May happen if the exec failes due to full-disk etc.
                if not exit_code:
                    self.logger.warn("exit_code=0, and %s don't exist!",
                                     self.run_dir)
                self.last_exit_msg = "exit_code=%i, full disk?" % exit_code
                return (exit_code, None)
            if (exit_code != 0
                    or (os.path.getsize(self.stdout_file) > 0
                        and not self.stdout_ok)
                    or os.path.getsize(self.stderr_file) > 0):
                newdir = "%s.%s/" % (self.run_dir, time.time())
                os.rename(self.run_dir, newdir)
                self.last_exit_msg = "exit_code=%i, check %s" % (exit_code,
                                                                 newdir)
                return (exit_code, newdir)
            self.last_exit_msg = "Ok"
            self._cleanup()
            return 1
        else:
            self.logger.debug("Wait returned %s/%s", pid, exit_code)
        return None

    def _cleanup(self):
        self.lockfile.release()
        os.unlink(self.stdout_file)
        os.unlink(self.stderr_file)

    def copy_runtime_params(self, other):
        super(System, self).copy_runtime_params(other)


class AssertRunning(System):

    def __init__(self, cmd, params=[], stdout_ok=0):
        super(AssertRunning, self).__init__(cmd, params, stdout_ok)
        self.wait = 0

    def setup(self):
        self.logger.info("setup %s" % self.id)
        try:
            self.lockfile.acquire(create=False)
        except LockExists:
            self.logger.info("%s already running" % self.id)
            return 0
        return 1


class UniqueActionAttrs(type):
    """Prevent two different classes from defining an Action with the
    same name (is there an easy way to also detect it in the same class?).
    """

    def __new__(cls, name, bases, dict_):
        known = dict([(k, name) for k, v in dict_.items()
                      if isinstance(v, Action)])
        for base in bases:
            for k in dir(base):
                if isinstance(getattr(base, k), Action):
                    if k in known:
                        raise ValueError("%s.%s already defined in %s" %
                                         (base.__name__, k, known[k]))
                    known[k] = base.__name__
        return type.__new__(cls, name, bases, dict_)


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
                if n not in all_jobs:
                    raise ValueError("Undefined pre-job '%s' in '%s'" %
                                     (n, name))
            for n in job.post:
                if n not in all_jobs:
                    raise ValueError("Undefined post-job '%s' in '%s'" %
                                     (n, name))

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
            graph[name] = node(name, job.pre, job.post)

        # remap names to object (it'll be easier later)
        for n in graph.itervalues():
            n.pre = [graph[key] for key in n.pre]
            n.post = [graph[key] for key in n.post]

        # scan all graph nodes and try to find cycles.
        for n in graph.itervalues():
            tmp = self.find_cycle(n)
            if tmp:
                raise ValueError("joblist has a cycle: %r"
                                 % [x.key for x in tmp])

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
