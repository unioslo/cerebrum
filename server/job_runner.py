#!/usr/bin/python
# $Id$
# TBD: Paralellitet: dersom det er flere jobber i ready_to_run køen
# som ikke har noen ukjørte pre-requisites, kan de startes samtidig.

jobs = {
    'import_from_lt':  Action(call=System('contrib/no/uio/import_from_LT.py', []),
                              max_freq=6*60*60)
    'import_ou':  Action(pre=['import_from_lt'],
                         call=System('contrib/no/uio/import_OU.py', []),
                         max_freq=6*60*60)
    'import_lt':  Action(pre=['import_ou', 'import_from_lt'],
                         call=System('contrib/no/uio/import_LT.py', []),
                         max_freq=6*60*60)
    'import_from_fs':  Action(call=System('contrib/no/uio/import_from_FS.py', []),
                              max_freq=6*60*60)
    'import_fs':  Action(pre=['import_from_fs'],
                         call=System('contrib/no/uio/import_FS.py', []),
                         max_freq=6*60*60)
    'process_students': Action(pre=['import_fs'],
                               call=System('contrib/no/uio/process_students.py', []),
                               max_freq=5*60)
    'backup': Action(call=System('contrib/backup.py'),
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
    def __init__(self, pre=None, post=None, call=call, max_freq=None, when=None):
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
          prerequisite for another job)."""
        
        self.pre = pre
        self.call = call
        self.max_freq = max_freq
        self.when = when

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

def insert_job(job):
    for j in job.prerequisites():
        insert_job(j)
    ready_to_run.append(job)

def find_ready_jobs():
    pass

def runner():
    while 1:
        # sleep until next job
        for job in ready_to_run:
            job.setup()
            job.execute()
            job.cleanup()

        # figure out what jobs to run next
        ready_to_run = []
        for job in find_ready_jobs():
            insert_job(job)
        
