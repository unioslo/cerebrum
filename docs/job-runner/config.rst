==================
Job configuration
==================

This document describes the job definition config for job-runner.

.. contents::
   :depth: 2
   :local:


The config module
==================
Job runner loads jobs from a Python config file.  This file can be given as a
command-line argument to the daemon, but by default, the ``scheduled_jobs``
python module is imported and used.

The module needs to expose a single ``get_jobs()`` function, which should return
a mapping of *job name* to an *Action* object.  The `defining a job`_ section
describes how to create a job with the *Action* object.

While you could implement the ``get_jobs()`` function yourself, but it is
recommended to use a *Jobs* object to provide this function.  See `grouping
jobs`_ for more details on this.

The following config module serves as a minimal example:
::

    from Cerebrum.modules.job_runner import job_actions

    class AllJobs(job_actions.Jobs):

        my_job = job_actions.Action(
            call=job_actions.System(
                "/usr/bin/bash",
                params=[
                    "-c", "date >> /tmp/logged-timestamps",
                ],
            ),
        )

    get_jobs = AllJobs().get_jobs



Defining a job
===============
Job definitions are *Action objects*
(``Cerebrum.modules.job_runner.job_actions.Action``), which describes job
limits, job scheduling, and the job implementation through a series of
attributes.  All attributes are *optional*:

``call``
    The job implementation.

    Must be a *CallableAction* object (usually *System*). See `Defining what to
    run`_ for more details.

    By default, this attribute is empty.  Jobs with an empty ``call``
    can be used in combination with e.g. ``when`` and ``post`` for scheduling
    and triggering other jobs.  These jobs are often referred to as *meta-jobs*.

``max_duration``
    Limit the runtime of this job to ``max_duration`` seconds.

    If the job runs for more than ``max_duration`` seconds, it will be
    terminated.  It is strongly recommended to set this to prevent jobs from
    deadlocking the queue.

    A good ``max_duration`` value depends on the job and its importance, but
    somewhere between 3-10 times the expected runtime is a good rule-of-thumb.

``when``
    When to schedule this job.

    This can either be a set interval, or a scheduling pattern (see scheduling_
    for details).

    By default, this attribute is empty, which means that the job will not be
    scheduled.

``notwhen``
    Prevent scheduling in this time window.

    Note that this is only a scheduling limitation that applies to jobs with a
    ``when`` attribute.  It does *not* prevent the job from running, or from
    being manually queued.

    If used, this attribute *must* be set to a ``When(time=Time(…))`` object.

``max_freq``
    The max frequency for a given job, in seconds.

    After a job runs, it will automatically prevent itself from being queued
    for *max_freq* seconds.  This limit applies to all interactions with the
    queue (not just scheduling).

    This attribute should normally be set to prevent jobs from being re-queued
    immediately if something goes wrong.

    Note, however, that this value can prevent legitimate queue-ing of the job,
    so the value should be set to a somewhat low value.

``multi_ok``
    Allow duplicates of this job in the queue.

    This is a legacy feature, and its behaviour is not well defined.  It
    generally not advised to use this attribute.

``nonconcurrent``
    An optional list of job names that *blocks* this job from running.

    Note that the attribute is *not* bi-directional.  For two jobs to be
    exclusive, they *both* need to add the name of the other job to their
    ``nonconcurrent`` attribute.

    Example: Given the jobs ``{'A': Action(nonconcurrent=["B"]), 'B':
    Action()}``, A cannot start if B is running, but B can start even though A
    is running.

``pre``
    An optional list of job names that should run *before* this job.

    Before adding *this* job to the queue, jobs from the pre-job list will be
    added to the queue.  Note that some of the pre-jobs may be omitted, as they
    are still subject to the `rules for adding jobs to the queue`_.

``post``
    An optional list of job names that should run *after* this job.

    After adding *this* job to the queue, jobs from the post-job list will be
    added to the queue.  Note that only jobs that pass the `rules for adding
    jobs to the queue`_ will get added.

``health``
    Can be set to a *HealthCheck* object with health check rules.

    Any rules from the HealthCheck object will be included in the health check
    report (see :doc:`health-check`).


Scheduling
-----------
Job Actions with a ``when`` attribute are subject to scheduling, and will
automatically be added to the queue.  Scheduling is specified with a *When
object* (``Cerebrum.modules.job_runner.times.When``), which can define schedules
by intervals or times:

- ``When(freq=120)``: Run at an interval - here every 2 minutes.
- ``When(time=Time(…))``: Run at a set time schedule.

``notwhen`` can be used to cancel out some of the times provided by ``when``.
This is typically used to *block* the job from running at set times with a
``notwhen=When(time=…)``, when the job runs periodically with a
``when=When(freq=…)``.

Note that scheduled jobs are still subject to the `rules for adding jobs to
the queue`_.

The *Time object* (``Cerebrum.modules.job_runner.times.Time`` defines a matrix
of weekday and time-of-day patterns.  These patterns are all lists of integers,
and are defined in the following attributes:

``mins`` (``list[int]``)
    A list of minute masks.  Each value must be 0-59, and will any time-of-day
    that is N minutes past the hour.  ``mins=[5, 10]`` matches both 5 minutes
    past the hour and 10 minutes past the hour.

    The default (``None``) will match every minute of the hour.

``hours`` (``list[int]``)
    A list of hour masks.  Each value must be 0-23, and will match a full hour
    of the day.  ``hours=[13, 14]`` will match from ``13:00`` to ``14:59``.

    The default (``None``) will match every hour of the day.

``wday`` (``list[int]``)
    A list of weekdays.  Each value must be 0-6, where 0 is Monday, and 6 is
    Sunday.  A value of ``wday=[0, 4]`` will match Mondays and Fridays.

    The default (``None``) will match every day of the week.

Additionally, the Time object may have a ``max_freq`` attribute.  This is an
optional time-of-day offset (in seconds) to limit how often this job may be
added to the queue by the scheduler.  This is a legacy feature, and should be
avoided.  Not to be confused with the ``Action.max_freq`` attribute.  See
`implementation details`_ for more info.

A job will be scheduled when the current time passes any time that is included
in the *Time* patterns.

Examples:

``Time()``
    Matches every minute, all day, every day.

``Time(min=[5, 25])``
    Every hour, at 5 minutes and 25 minutes past the hour, every day of the
    week.

``Time(min=[0], hour=[1])``
    Every day at 01:00.

``Time(min=None, hour=[1])``
    Every minute from 01:00 to 01:59, all days of the week.

``Time(min=[30], hour=[6, 18], wday=[1])``
    Evey *Tuesday*, at 06:30 *and* at 18:30.


Implementation details
~~~~~~~~~~~~~~~~~~~~~~~
The queue figures out if a job should be scheduled by calling:
``Action.next_delta(prev_time: int, curr_time: int) -> int``.

``prev_time``
    is the timestamp for when the previous iteration of this job was finished.

    For e.g. new jobs, this is just set to the Unix epoch (``0``).

``curr_time``
    is the timestamp to calculate for.  This is typically just ``time.time()``
    when checking if a job should be scheduled.

return value
    Number of seconds until this job should be queued.  The job is queued when
    this value is *negative*.

This is where the ``Time.max_freq`` comes into play.  It simply *pretends* that
the job previously finished later than it actually did, which prevents
re-scheduling for ``max_freq`` seconds.


Rules for adding jobs to the queue
-----------------------------------
A job can only be added to the job queue if:

- It's not currently queued (can be overridden with ``Action.multi_ok``)
- It did't run in the last ``Action.max_freq`` seconds.
- It's not currently running


Queue processing
-----------------
The job queue is an ordered list of jobs to run.  The job-runner daemon will
process this queue in timed intervals, and in each iteration it will attempt to
start all jobs in the queue.

Jobs in the may have *blockers* that prevents them from starting.  A job with
blockers will simply be skipped in the current iteration, and re-tried in the
next.  These blockers are:

- The queue is paused.

- Too many jobs are currently running
  (``cereconf.JOB_RUNNER_MAX_PARALELL_JOBS``)

- A pre-requisite (``Action.pre``) is also in the queue, or currently running

- One of the ``nonconcurrent`` jobs are running.

.. todo:: More checks

   There are some more checks here, especially in the pre/post job list, but
   they're a bit dense.  This list should be reviewed.

Note that jobs can also be *forced*, which omits these checks.  Forced jobs
will not appear as *running* when checking if other jobs can be added to the
queue.


Defining what to run
---------------------
The main use case for *Actions*, is to run and monitor a subprocess.

This is done using a *System object*
(``Cerebrum.modules.job_runner.job_actions.System``), which takes three
arguments:
::

    System(cmd, params=None, stdout_ok=False)

Where:

``cmd``
    is the command to run, or ``argv[0]``.

``params``
    is an optional list of arguments for the *cmd*.  All values must be strings.

    Note that *params* also supports callables that takes no arguments and
    returns a string, for arguments that needs to be generated.

``stdout_ok``
    defines if output to *stdout* is normal behaviour for this command.  By
    default it is ``False``, which means that any stdout is registered as
    abnormal behaviour, and any output to stdout means that the workdir will be
    kept around for later inspection (see :doc:`/maintenance/job-runner`).


Writing the config
===================
Some useful tips to write and organize a ``scheduled_jobs``-like config file.

Grouping jobs
--------------
Normally, the ``get_jobs()`` would be implemented using a subclass of *Jobs*
(``Cerebrum.modules.job_runner.job_actions.Jobs``).

The *Jobs* class is typically used to group jobs together.  Any *Action*
defined as a class attribute in a *Jobs* class, will be returned by the
``Jobs.get_jobs()`` method:
::

    class FooJobs(Jobs):
        foo_all = Action(post=["foo_pre", "foo_main", "foo_post"])

        foo_pre = Action()
        foo_main = Action()
        foo_post = Action()


    class AllJobs(FooJobs):
        unrelated_job = Action()


    get_jobs = AllJobs().get_jobs


Inspecting the config
----------------------
When using *Jobs* to group *Actions*, you can make the config module *runnable*
using the ``Cerebrum.modules.job_runner.job_utils.pretty_jobs_presenter``:
::

    if __name__ == '__main__':
        pretty_jobs_presenter(AllJobs(), None)


This turns the config into a script with some convenient utility functions:
::

    $ python scheduled_jobs.py --help
    usage: scheduled_jobs.py [-h] [-l | -v | -s NAME]

    Show job runner config

    optional arguments:
      -h, --help            show this help message and exit
      -l, --list            List all the jobs
      -v, --list-verbose    List jobs verbosely
      -s NAME, --show-job NAME
                            Show a given job NAME


Referencing jobs
-----------------
When referring to other jobs using the ``Action.pre``, ``Action.post``, and
``Action.nonconcurrent`` attributes, all the referenced job names *must* exist
in the final config.

It is generally best-practice to keep dependencies as *simple* as possible.
Note that pre-jobs and post-jobs don't have to finish *successfully* for the
dependency to be fulfilled!


Scheduling conflicts
---------------------
Scheduled jobs should generally have a ``max_freq``, but this can also prevent
jobs or dependencies from running.  A useful pattern in these cases is to
schedule a *meta-job* with a ``max_freq``, which then queues non-scheduled jobs
without a ``max_freq``.


``to_seconds``
---------------
``Cerebrum.utils.date.to_seconds`` is useful for making attributes with values
in *seconds* more readable:
::

    my_job = Action(
        max_duration=to_seconds(minutes=15),
        when=When(freq=to_seconds(hours=8)),
        max_freq=to_seconds(minutes=3),
        health=HealthCheck(check_overdue=to_seconds(days=1, hours=12)),
    )
