===============
scheduled_jobs
===============

Job runner loads jobs from a Python config file.  This file can be given as a
command-line argument to the daemon, but by default, the ``scheduled_jobs``
python module is imported and used.

The module needs to expose a single ``get_jobs()`` function, which should return
a mapping of *job name* to a ``Cerebrum.modules.job_runner.job_actions.Action``
object.

The following config module serves as a basic example.  It defines a single job
that is *not* scheduled:
::

    from Cerebrum.modules.job_runner.job_actions import (
        Action,
        System,
    )

    def get_jobs():
        return {
            'my_job': Action(
                call=System(
                    "/usr/bin/bash",
                    params=[
                        "-c", "date >> /tmp/logged-timestamps",
                    ],
                ),
            ),
        }



Defining a job
===============
Job definitions are *Action* objects
(``Cerebrum.modules.job_runner.job_actions.Action``).  All the *Action*
attributes are optional, and defaults to ``None`` or ``False``.


``call``
    The actual job implementation.

    Must be a *CallableAction*
    (``Cerebrum.modules.job_runner.job_action.CallableAction``) . See `Defining
    what to run`_ for more details.

    This value can be empty.  When empty, the job turns into a *meta-job*, and
    is often used in combination with ``when`` for scheduling, and ``post`` for
    triggering other jobs.

``max_duration``
    Limit the runtime of this action to ``max_duration`` seconds.

    If the job runs for more than ``max_duration`` seconds, it will be
    terminated.  It is strongly recommended to set this to prevent jobs from
    deadlocking the queue.

    A good ``max_duration`` value depends on the job and its importance, but
    somewhere between 3-10 times the expected runtime is a good rule-of-thumb.

``when``
    When to schedule this job.

    This can either be a set interval, or a scheduling pattern (see scheduling_
    for details).

    When unset, the job will not be scheduled.

``notwhen``
    Prevent scheduling in this time window.

    Note that this is only a scheduling *limitation* that applies to Actions
    with a ``when`` attribute.  It does *not* prevent the job from running, or
    from being manually queued.

    This uses the same value as ``when``, but *must* have a ``when.time``
    attribute.

``max_freq``
    The max frequency for a given job, in seconds.

    After an Action runs, it will automatically prevent itself from being queued
    for *max_freq* seconds.

    This *limit* applies to all interactions with the queue (not just
    scheduling).

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
    exclusive, they *both* need to exclude the other in their ``nonconcurrent``
    attribute.

    Example: Given the jobs ``{'A': Action(nonconcurrent=["B"]), 'B':
    Action()}``, A cannot start if B is running, but B can start even though A
    is running.

``pre``
    An optional list of job names that should run *before* this job.

    Before adding *this* job to the queue, jobs from the pre-job list will be
    added to the queue.  Note that some of the pre-jobs may be omitted, as they
    are still subject to the `rules for adding a job to the queue`_.

``post``
    An optional list of job names that should run *after* this job.

    After adding *this* job to the queue, jobs from the post-job list will be
    added to the queue.  Note that only jobs that pass the `rules for adding a
    job to the queue`_ will get added.

``health``
    Can be set to a ``HealthCheck`` object with health check rules.

    If the HealthCheck adds a health check rule, this job will be included in
    the health check report (see :doc:`health-check`).


Scheduling
-----------
Job Actions with a ``when`` attribute are subject to scheduling, and will
automatically be added to the queue at set intervals.

Scheduling is specified with a *When* object
(``Cerebrum.modules.job_runner.times.When``), which can define schedules by
intervals or times:

- ``When(freq=120)``: Run at an inteval - here every 2 minutes.
- ``When(time=Time(…))``: Run at a set time schedule.

``notwhen`` can be used to cancel out some of the times provided by ``when``..
This is typically used to *block* the job from running at set time schedules,
with a ``notwhen=When(time=…)``, when the job runs periodically at set
intervals with a ``when=When(freq=..)``.

Note that scheduled jobs are still subject to the `rules for adding a job to
the queue`_.

The ``Time(min=None, hour=None, wday=None, max_freq=None)`` defines a matrix of
weekdays and times-of-day patterns, where each of the attributes ``min``,
``hour`` and ``wday`` are lists of integers.

A job will be scheduled when the current time passes one of the times that
match *any* value in *all* of these arguments.

The default value, ``None`` matches all possible values.  This means that a
default ``Time()`` object without any arguments, defines a scheduling pattern
that triggers *every minute*.

The scheduling patterns are best described by examples:

``Time(min=[5, 25])``
    Every hour, at 5 minutes and 25 minutes past the hour, every day of the
    week.

``Time(min=[0], hour=[1])``
    Every day at 01:00.

``Time(min=None, hour=[1])``
    Every minute from 01:00 to 01:59, all days of the week.

``Time(min=[30], hour=[6, 18], wday=[1])``
    Evey *tuesday* (wday=1), at 06:30 *and* at 18:30.

.. note::
   The optional ``Time.max_freq`` should not be confused with the
   ``Action.max_freq`` argument.  ``Time.max_freq`` is a legacy feature that
   prevents the job from being re-scheduled for max_freq seconds after
   finishing a run.

   See `implementation details`_ for more info.


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
    Number of seconds until next run.  If this is negative, the job should be
    queued.

This is where the ``Time.max_freq`` comes into play.  It simply *pretends* that
the job previously finished later than it actually did, which prevents
re-scheduling for ``max_freq`` seconds.


Rules for adding a job to the queue
------------------------------------
A job can only be added to the job queue if:

- It's not currently queued (can be overridden with ``Action.multi_ok``)
- It did't run in the last ``Action.max_freq`` seconds.
- It's not currently running


Queue processing
-----------------
The job queue is an ordered list of jobs to run, and any job in the queue will
be started unless:

- The queue is paused.

- Too many jobs are currently running
  (``cereconf.JOB_RUNNER_MAX_PARALELL_JOBS``)

- A pre-requisite (``Action.pre``) is also in the queue, or currently running

- One of the ``nonconcurrent`` jobs are running.

.. todo:: More checks

   There are some more checks here, especially in the pre/post job list, but
   they're a bit dense.  This list should be reviewed

Note that jobs can also be *forced*, which omits these checks.  Forced jobs
will not appear as *running* when checking if other jobs can be added to the
queue.


Defining what to run
---------------------
The main use case for *Actions*, is to run a *System* call.

The *System* call takes three arguments:

::

    System(cmd, params=None, stdout_ok=False)

``cmd`` is the command to run, or ``argv[0]``.

``params`` is an optional list of arguments for the *cmd*.  All values must be
strings.  Note that *params* also supports callables that takes no arguments
and returns a string, for arguments that needs to be generated.

``stdout_ok`` defines if output to *stdout* is normal behaviour for this
command.  By default it is ``False``, which means that any stdout is registered
as abnormal behaviour, and any output to stdout means that the workdir will be
kept around for later inspection (see :doc:`/maintenance/job-runner`).


Writing the config
===================
Some useful tips to write and organize a ``scheduled_jobs``-like config file.

Grouping jobs
--------------
Normally, the ``get_jobs()`` would be implemented using a
``Cerebrum.modules.job_runner.job_actions.Jobs`` subclass.

The ``Jobs`` class is typically used to *group* jobs together.  Any *Action*
defined as a class attribute in a *Jobs* class, will be returned by the
``Jobs.get_jobs()`` method:
::

    class MyJobs(Jobs):

        my_job = Action(
            call=System(
                "/usr/bin/bash",
                params=[
                    "-c", "date >> /tmp/logged-timestamps",
                ],
            ),
        )


    get_jobs = MyJobs().get_jobs


Inspecting the config
----------------------
When using *Jobs* to group *Actions*, you can make the config module *runnable*
using the ``Cerebrum.modules.job_runner.job_utils.pretty_jobs_presenter``:
::

    if __name__ == '__main__':
        pretty_jobs_presenter(MyJobs(), None)


This adds some argument parsing and useful utility functions to the config
module:
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
``Cerebrum.utils.date.to_seconds`` is useful for keeping the various arguments
values in *seconds* readable:
::

    my_job = Action(
        max_duration=to_seconds(minutes=15),
        when=When(freq=to_seconds(hours=8)),
        max_freq=to_seconds(minutes=3),
        health=HealthCheck(check_overdue=to_seconds(days=1, hours=12)),
    )
