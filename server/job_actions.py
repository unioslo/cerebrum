#!/usr/bin/env python2.2

# $Id$
import popen2
import fcntl
import os
import select

LockExists = 'LockExists'

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

        self.pre = pre
        self.call = call
        self.max_freq = max_freq
        self.when = when
        self.post = post
        self.multi_ok = multi_ok


class CallableAction(object):
    """Abstract class representing the call parameter to Action"""

    def __init__(self):
        self.id = None
        
    def setup(self):
        pass

    def execute(self):
        raise RuntimeError, "Override CallableAction.execute"

    def cleanup(self):
        pass

    def set_id(self, id):
        self.id = id
        self.locfile_name = "job-runner-%s.lock" % id

    def set_logger(self, logger):
        self.logger = logger

    def check_lockfile(self):
        if os.path.isfile(self.locfile_name):
            f = open(self.locfile_name, 'r')
            pid = f.readline()
            if(pid.isdigit()):
                os.kill(int(pid), 0)
                raise LockExists

    def make_lockfile(self):
        f=open(self.locfile_name, 'w')
        f.write("%s" % os.getpid())
        f.close()

class ProcessHelper(object):
    def execute(cmd, stdout_fname, stderr_fname):
        """Execute cmd (a list), redirecting stdout and stderr.
        Returns the pid of the new process."""
        pid = fork()
        if pid:
            return pid
        os.system(self.cmd)
        sys.exit(0)
    execute = staticmethod(execute)

class AssertRunning(CallableAction):
    """Assert that a program is running, if it is not: start it"""
    
    def __init__(self, cmd, params=[], stdout_ok=0, warn_notrunning=0):
        super(AssertRunning, self).__init__()
        self.cmd = cmd
        self.params = list(params)
        self.stdout_ok = stdout_ok
        self.warn_notrunning = warn_notrunning

    def execute(self):
        # TODO: Check if process is running, if not: start it (but
        # avoid zombies)
        try:
            self.check_lockfile()
        except LockExists:
            print "NO exec, already running"
            return  # Process already running, OK
        if not os.fork():
            db.close()
            self.make_lockfile()
            # TBD: Could we exec here?
            os.system(self.cmd)
            os.unlink(self.locfile_name)
            sys.exit(0)
            
class System(CallableAction):
    """Run a command with the specified parameters.  Return values
    other than 0, as well as any data on stdout/stderr is considered
    an error"""

    def __init__(self, cmd, params=[], stdout_ok=0):
        super(System, self).__init__()
        self.cmd = cmd
        self.params = list(params)
        self.stdout_ok = stdout_ok

    def makeNonBlocking(fd):
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        try:
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
        except AttributeError:
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.FNDELAY)
    makeNonBlocking = staticmethod(makeNonBlocking)

    def execute(self):
        # TODO: We will use a lot of mem if lots is written on stdout/stderr

        p = self.params[:]
        # For debug
        p.insert(0, self.cmd)
        self.logger.debug("Run: %s" % p)
        # Redirect stdout/stderr
        # From http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52296
        child = popen2.Popen3(p, 1)
        child.tochild.close()
        outfile = child.fromchild
        outfd = outfile.fileno()
        errfile = child.childerr
        errfd = errfile.fileno()
        System.makeNonBlocking(outfd)
        System.makeNonBlocking(errfd)
        outdata = errdata = ''
        outeof = erreof = 0
        while 1:
            ready = select.select([outfd,errfd],[],[]) # wait for input
            if outfd in ready[0]:
                outchunk = outfile.read()
                if outchunk == '': outeof = 1
                outdata += outchunk
            if errfd in ready[0]:
                errchunk = errfile.read()
                if errchunk == '': erreof = 1
                errdata += errchunk
            if outeof and erreof: break
            select.select([],[],[],.1) # give a little time for buffers to fill
        err = child.wait()
        if err != 0 or (len(outdata) != 0 and self.stdout_ok == 0) or len(errdata) != 0:
            # TODO: What shall we do here?
            self.logger.error("Error running command %s, ret=%d/%s, stdout=%s, stderr=%s" %
                              (p, err, os.strerror(err), outdata, errdata))
            
