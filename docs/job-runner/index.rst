===========
job-runner
===========

*job-runner* is the job scheduler for Cerebrum, and is used to trigger the
various Cerebrum *scripts*, as well as other tasks.


Daemon
=======
Job-runner should generally run in all Cerebrum deployments, although other
schedulers *could* be used in its place.

The daemon is started using ``servers/job_runner/job_runner.py``.  A typical
invocation:
::

    /cerebrum/bin/python /cerebrum/sbin/job_runner.py


Options:

``--health-report`` ``FILE``
    Periodically generate and write a health report to ``FILE``.

    This is typically ``<sys.prefix>/var/run/job-runner-health.json``

``--socket`` ``FILE``
    Use a non-default socket for IPC.

    Note that any client must also provide this path in order to communicate
    with the daemon.

    This defaults to ``cereconf.JOB_RUNNER_SOCKET``

``--config`` ``SPEC``
    Use the job definitions provided in ``SPEC``.

    ``SPEC`` can either be the path to a python file, or an importable module
    name.

    By default, the config module ``scheduled_jobs`` is used to load jobs.


Client
=======
The daemon_ exposes an IPC socket on the local file system for communication.
This socket can be used for interacting with job-runner from the host it runs
on.

:doc:`job-runner-cli` is the default client for communicating with the daemon
over the IPC socket.


Documents
==========
.. toctree::
   :maxdepth: 1
   :glob:

   *
