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

import cerebrum_path
import cereconf
import scheduled_jobs

from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory
from Cerebrum import Errors

debug_time = 0        # increase time by N seconds every second
max_sleep = 300
current_time = time.time()
db = Factory.get('Database')()

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")

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

class When(object):
    def __init__(self, freq=None, time=None):
        """Indicates that a job should be ran either with a specified
        frequency, or at the specified time"""
        assert freq is not None or time is not None
        assert not (freq is not None and time is not None)
        self.freq = freq
        self.time = time

    def next_delta(self, last_time, current_time):
        """Returns # seconds til the next time this job should run
        """
        if self.freq is not None:
            return last_time + self.freq - current_time
        else:
            times = []
            for t in self.time:
                d = t.next_time(last_time)
                times.append(d + last_time - current_time)
            return min(times)

class Time(object):
    def __init__(self, min=None, hour=None, wday=None):
        """Emulate time part of crontab(5), None=*"""
        self.min = min
        if min is not None:
            self.min.sort()
        self.hour = hour
        if hour is not None:
            self.hour.sort()
        self.wday = wday
        if wday is not None:
            self.wday.sort()

    def _next_list_value(self, val, list, size):
        for n in list:
            if n > val:
                return n, 0
        return min(list), 1

    def next_time(self, num):
        """Return the number of seconds until next time after num"""
        hour, min, sec, wday = (time.localtime(num))[3:7]

        add_week = 0
        for i in range(10):
            if self.wday is not None and wday not in self.wday:
                # finn midnatt neste ukedag
                hour = 0
                min = 0
                t, wrap = self._next_list_value(wday, self.wday, 6)
                wday = t
                if wrap:
                    add_week = 1

            if self.hour is not None and hour not in self.hour:
                # finn neste time, evt neste ukedag
                min = 0
                t, wrap = self._next_list_value(hour, self.hour, 23)
                hour = t
                if wrap:
                    wday += 1
                    continue

            if self.min is not None and min not in self.min:
                # finn neste minutt, evt neste ukedag
                t, wrap = self._next_list_value(min, self.min, 59)
                min = t
                if wrap:
                    hour += 1
                    continue

            # Now calculate the diff
            old_hour, old_min, old_sec, old_wday = (time.localtime(num))[3:7]
            week_start_delta = (old_wday*24*3600 + old_hour*3600 + old_min*60 + old_sec)

            return add_week*7*24*3600 + wday*24*3600 + hour*3600 + min*60 - week_start_delta
        raise ValueError, "Programming error for %i" % num

def makeNonBlocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    try:
	fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
    except AttributeError:
	fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.FNDELAY)

class CallableAction(object):
    """Abstract class representing the call parameter to Action"""

    def setup(self):
        pass

    def execute(self):
        raise RuntimeError, "Override CallableAction.execute"

    def cleanup(self):
        pass

class System(CallableAction):
    """Run a command with the specified parameters.  Return values
    other than 0, as well as any data on stdout/stderr is considered
    an error"""

    def __init__(self, cmd, params=[], stdout_ok=0):
        self.cmd = cmd
        self.params = list(params)
        self.stdout_ok = stdout_ok

    def execute(self):
        # TODO: We will use a lot of mem if lots is written on stdout/stderr

        p = self.params[:]
        # For debug
        p.insert(0, self.cmd)
        logger.debug("Run: %s" % p)
        # Redirect stdout/stderr
        # From http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52296
        child = popen2.Popen3(p, 1)
        child.tochild.close()
        outfile = child.fromchild
        outfd = outfile.fileno()
        errfile = child.childerr
        errfd = errfile.fileno()
        makeNonBlocking(outfd)
        makeNonBlocking(errfd)
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
            logger.error("Error running command %s, ret=%d/%s, stdout=%s, stderr=%s" %
                         (p, err, os.strerror(err), outdata, errdata))

def insert_job(job):
    """Recursively add jobb and all its prerequisited jobs.

    We allways process all parents jobs, but they are only added to
    the ready_to_run queue if it won't violate max_freq."""

    if all_jobs[job].pre is not None:
        for j in all_jobs[job].pre:
            insert_job(j)

    if job not in ready_to_run or all_jobs[job].multi_ok:
        if (all_jobs[job].max_freq is None
            or current_time - last_run.get(job, 0) > all_jobs[job].max_freq):
            ready_to_run.append(job)

    if all_jobs[job].post is not None:
        for j in all_jobs[job].post:
            insert_job(j)

def find_ready_jobs(jobs):
    """Populates the ready_to_run queue with jobs.  Returns number of
    seconds to next event (if positive, ready_to_run will be empty)"""
    global current_time
    if debug_time:
        current_time += debug_time
    else:
        current_time = time.time()
    min_delta = 999999
    for k in jobs.keys():
        delta = current_time - last_run.get(k, 0)
        # print "  %d for %s / %s" % (delta, k, jobs[k].when)
        if jobs[k].when is not None:
            n = jobs[k].when.next_delta(last_run.get(k, 0), current_time)
            if n <= 0:
                insert_job(k)
            min_delta = min(n, min_delta)
    return min_delta

# There is a python supplied sched module, but we don't use it for now...
def runner():
    global all_jobs, ready_to_run, last_run
    all_jobs = scheduled_jobs.get_jobs()
    ready_to_run = []
    last_run = get_last_run()
    while 1:
        for job in ready_to_run:
            if all_jobs[job].call is not None:
                all_jobs[job].call.setup()
                all_jobs[job].call.execute()
                all_jobs[job].call.cleanup()
            if debug_time:
                last_run[job] = current_time
            else:
                last_run[job] = time.time()
            update_last_run(job, last_run[job])
        # figure out what jobs to run next
        ready_to_run = []
        delta = find_ready_jobs(all_jobs)
        logger.debug("New queue (delta=%s): %s" % (delta, ", ".join(ready_to_run)))
        if(delta > 0):
            if debug_time:
                time.sleep(1)
            else:
                time.sleep(min(max_sleep, delta))      # sleep until next job

def get_last_run():
    ret = {}
    for r in db.query(
        """SELECT id, timestamp
        FROM [:table schema=cerebrum name=job_ran]"""):
        ret[r['id']] = r['timestamp'].ticks()
    logger.debug("get_last_run: %s" % ret)
    return ret

def update_last_run(id, timestamp):
    timestamp = db.TimestampFromTicks(timestamp)
    logger.debug("update_last_run(%s, %s)" % (id, timestamp))

    try:
        db.query_1("""
        SELECT 'yes'
        FROM [:table schema=cerebrum name=job_ran]
        WHERE id=:id""", locals())
    except Errors.NotFoundError:
        db.execute("""
        INSERT INTO [:table schema=cerebrum name=job_ran]
        (id, timestamp)
        VALUES (:id, :timestamp)""", locals())
    else:
        db.execute("""UPDATE [:table schema=cerebrum name=job_ran]
        SET timestamp=:timestamp
        WHERE id=:id""", locals())
    db.commit()
## CREATE TABLE job_ran
## (
##   id           CHAR VARYING(32)
##                CONSTRAINT job_ran_pk
##                PRIMARY KEY,
##   timestamp    TIMESTAMP  # datetime doesn't work with pyPgSQL
##                NOT NULL
##   );

if __name__ == '__main__':
    runner()
