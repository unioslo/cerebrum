#!/usr/bin/env python2.2

# $Id$
# TBD: Paralellitet: dersom det er flere jobber i ready_to_run køen
# som ikke har noen ukjørte pre-requisites, kan de startes samtidig.

import time
debug_time = 60
current_time = time.time()
run_once = 1  # Only for debugging

def get_jobs():
    return {
        'import_from_lt':  Action(call=System('contrib/no/uio/import_from_LT.py', []),
                                  max_freq=6*60*60),
        'import_ou':  Action(pre=['import_from_lt'],
                             call=System('contrib/no/uio/import_OU.py', []),
                             max_freq=6*60*60),
        'import_lt':  Action(pre=['import_ou', 'import_from_lt'],
                             call=System('contrib/no/uio/import_LT.py', []),
                             max_freq=6*60*60),
        'import_from_fs':  Action(call=System('contrib/no/uio/import_from_FS.py', []),
                                  max_freq=6*60*60),
        'import_fs':  Action(pre=['import_from_fs'],
                             call=System('contrib/no/uio/import_FS.py', []),
                             max_freq=6*60*60),
        'process_students': Action(pre=['import_fs'],
                                   call=System('contrib/no/uio/process_students.py', []),
                                   max_freq=5*60),
        'backup': Action(call=System('contrib/backup.py', []),
                         max_freq=23*60*60),
        'rotate_logs': Action(call=System('contrib/rotate_logs.py'),
                              max_freq=23*60*60),
        'daily': Action(pre=['import_lt', 'import_fs', 'process_students'],
                        call=None,
                        when=When(time=[Time(min=10, hour=1)]),
                        post=['backup', 'rotate_logs']),
        'generate_passwd': Action(call=System('contrib/generate_nismaps', []),
                                  max_freq=5*60),
        'dist_passwords': Action(pre=['generate_passwd'],
                                 call=System('.../passdist.pl', []),
                                 max_freq=5*60, when=When(freq=10*60))
        }

class Action(object):
    def __init__(self, pre=None, post=None, call=None, max_freq=None, when=None):
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

          If max_freq is None, the job will allways run.  If when is
          None, the job will only run if it is a prerequisite of
          another job."""
        
        self.pre = pre
        self.call = call
        self.max_freq = max_freq
        self.when = when
        self.post = post

    def setup(self):
        if self.call is not None:
            self.call.setup()

    def execute(self):
        if self.call is not None:
            self.call.execute()

    def cleanup(self):
        if self.call is not None:
            self.call.cleanup()

class When(object):
    def __init__(self, freq=None, time=None):
        """Indicates that a job should be ran either with a specified
        frequency, or at the specified time"""
        self.freq = freq
        self.time = time

class Time(object):
    def __init__(self, sek=0, min=None, hour=None, day=None, mon=None, weekday=None):
        """Emulate time part of crontab(5), None=*"""
        self.min = min
        self.hour = hour
        self.day = day
        self.mon = mon
        self.weekday = weekday

class System(object):
    def __init__(self, cmd, params=None):
        self.cmd = cmd
        self.params = params

    # TODO: simple versions of these methods should be in a superclass
    def setup(self):
        pass

    def execute(self):
        # print "Executing: %s" % self.cmd
        pass
    
    def cleanup(self):
        pass

def insert_job(job):
    """Recursively add jobb and all its prerequisited jobs.

    We allways proecss all parents jobs, but they are only added to
    the ready_to_run queue if it won't violate max_freq."""
    
    if all_jobs[job].pre is not None:
        for j in all_jobs[job].pre:
            insert_job(j)

    if job not in ready_to_run:
        if (all_jobs[job].max_freq is None
            or current_time - last_run.get(job, 0) > all_jobs[job].max_freq):
            ready_to_run.append(job)

    if all_jobs[job].post is not None:
        for j in all_jobs[job].post:
            insert_job(j)

def is_when_ok(job, current_time):
    """Check if this jobs When object indicates that is should run now
    """

    # TBD: It is probably better to return # seconds to next when,
    # then we would know how long to sleep for the action to succeed.

    if job.when is not None:
        if job.when.freq is not None:
            return 1
        else:
            # TODO: Check jobs[k].when.time
            if run_once:
                return 1

def find_ready_jobs(jobs):
    global current_time, run_once
    ret = []
    if debug_time:
        current_time += debug_time
    else:
        current_time = time.time()
    for k in jobs.keys():
        delta = current_time - last_run.get(k, 0)
        print "  %d for %s / %s" % (delta, k, jobs[k].when)

        if is_when_ok(jobs[k], current_time):
            insert_job(k)
    run_once = 0
    print "r: %i" % len(ret)
    return ret

# There is a python supplied sched module, but we don't use it for now...
def runner():
    global all_jobs, ready_to_run, last_run
    all_jobs = get_jobs()
    ready_to_run = []
    last_run = {}
    while 1:
        # sleep until next job
        time.sleep(1)
        for job in ready_to_run:
            all_jobs[job].setup()
            all_jobs[job].execute()
            all_jobs[job].cleanup()
            if debug_time:
                last_run[job] = current_time
            else:
                last_run[job] = time.time()
            print "LR: %s" % job
        # figure out what jobs to run next
        ready_to_run = []
        find_ready_jobs(all_jobs)
        print "New queue:\n   %s" % "\n   ".join(ready_to_run)

if __name__ == '__main__':
    runner()
