===========
job-runner
===========

This document is about removing *old workdirs* created by job-runner.


About job-runner
=================
The Cerebrum scheduler, ``job-runner``, creates a new workdir for each
job/process it starts.  In addition to being the workdir for processes started
by the job, output to stdout or stderr is written to their own respective file
in this directory.

The directory is normally deleted after the job completes, but is *archived*
(renamed and kept indefinitely) if the job fails for any reason.


Deleting old workdirs
======================
Keeping these directories around isn't really all that useful, and can cause
problems in the long run.  To solve this, the utility script
``contrib/utils/delete-job-runner-workdirs.py`` should be added as a additional
job in job-runner to remove old and obsolete workdirs.

This script simply deletes all archived job-runner workdirs after they reach a
given age.  You would typically run something like:
::

    python contrib/utils/delete-job-runner-workdirs.py \
        --logger-name cronjob \
        --logger-level INFO \
        --min-age 14 \
        --workdir <cereconf.JOB_RUNNER_LOG_DIR> \
        --commit

``--min-age`` is used to specify how many days an archived workdir should be
kept around before being deleted.  The timestamp suffix of the archive directory
name is used to decide its age.

``--workdir`` tells the script where the job-runner workdirs are placed.  This
defaults to ``cereconf.JOB_RUNNER_LOG_DIR``, but it can be useful (for
readability) to specify this value in explicitly in a job definition.

``--commit`` tells the script to actually delete the matching workdirs.  By
default the script runs in dryrun mode which doesn't touch the file system.
Running in dryrun mode is only useful for sanity checking the cli-arguments
and/or testing the script behaviour.
