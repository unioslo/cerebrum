===============
job-runner-cli
===============

The job-runner-cli client (``contrib/clients/job-runner-cli.py``) is the default
client for communicating with the *job-runner* daemon.

Communication uses an IPC socket exposed by the daemon.  By default, both the
client and server uses the ``cereconf.JOB_RUNNER_SOCKET``.


Usage
======
::

    python job-runner-cli.py [options] <command> [command-options]

Options:

``--socket`` ``FILE``
    Use a non-default socket for IPC.

    Only needed if the daemon uses a non-standard socket location.

``--timeout`` ``TIMEOUT``
    Set a read timeout for command calls (in seconds).


Commands
=========

reload
-------
Reloads the current job-runner config file.

Note that this does *not* handle job removals well.  When removing job
definitions, the daemon should be restarted.


quit
-----
Graceful shutdown.

This will empty the current queue, but wait for any *running* jobs to complete
before shutting down.


kill
-----
This is the same as quit_, but will kill any jobs that are still running after 5
seconds.


status
-------
Show the current job-runner state.

Dumps the current state in four sections:

- *Run-queue* — any currently running jobs
- *Ready-jobs* - pending jobs that are ready to run (the job-runner queue)
- *Threads* - a list of all job-runner threads, for debugging
- *Known jobs* - A list of all the jobs known to job-runner

The output also indicates if queue processing is paused.


pause
------
Pause the job-runner queue.  This prevents pending jobs from starting.


resume
-------
Resume the job-runner queue. This cancels a previous pause_ command.


report
-------
Get an up-to-date health check report.


run
----
Manually add a job to the job-runner queue.

The default mode is to *force* a job.  This means that its limits and
dependencies (``max_freq``, ``pre``, ``post``, ``nonconcurrent``) are ignored,
and the job will also limit interference with the regular job scheduling.

To queue a job normally, while respecting its limits and dependencies, the
``--with-deps`` flag must be used:
::

    python job-runner-cli.py run --with-deps my_job

Note that this is likely to do nothing if the job runs very often, or has e.g. a
high ``max_freq``.


show
-----
Show a job definition.

This shows the named job definition in a human readable format.  Example:
::

    Status: not running, not queued
    Last start: Tue Aug 11 12:00:00 2026
    Last done: Tue Aug 11 12:30:00 2026
    Last status: ok
    Command: bash -c 'echo "hello world" > /dev/null'
    Pre-jobs: []
    Post-jobs: []
    Non-concurrent jobs: []
    When: freq=00:05:00, max-freq: 180
    Max duration: 5.0 minutes


dump
-----
Show all defined jobs in a tree-like view.
