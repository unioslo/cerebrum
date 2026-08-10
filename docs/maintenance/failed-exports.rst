===============
Failed exports
===============

This document is about removing *failed exports* created
by ``Cerebrum.modules.atomicfile``.


About atomicfile
=================
Most files produced by Cerebrum-scripts are written by a
``Cerebrum.utils.atomicfile`` file-like class.  These classes writes output to a
temporary file, which only replaces the *target filename* after successfully
closing the file stream.

This is done to prevent partially written files from replacing earlier,
successfully written files, and in some cases to run sanity checks on the
result before potentially replacing the *target filename*.

If a script fails before closing an atomicfile, the *temporary file* will be
kept indefinitely for debugging.


Deleting temporary files
=========================
Just as with :doc:`job-runner`, keeping these failed files around will cause
problems in the long run, so we have a utility script for dealing with them.

The cleanup script, ``contrib/utils/delete-temp-files.py``, will recursively
search a given directory tree for files with a given glob-like pattern, and
delete them after some time.  As with other file cleanup scripts, this should be
added as a job-runner job.

The job should run something like:
::

    python contrib/utils/delete-temp-files.py
        --logger-name cronjob
        --logger-level INFO
        --glob-pattern "*.json.?????"
        --glob-pattern "*.ldif.?????"
        --glob-pattern "*.pickle.?????"
        --glob-pattern "*.xml.?????"
        --min-age 7
        --commit
        /cerebrum/var/cache/

``--glob-pattern`` adds a filename pattern to delete.  Temporary files created
by atomicfile will use the same name as the *target file*, but with a randomized
five-letter suffix/extension.

``--min-age`` is used to specify how many days the matching files should be kept
around before being deleted.  The file *mtime* is used to decide its age.
Note that a minimum age should always be provided.  If omitted or set to ``0``,
you risk removing a temporary file that is currently being written.

``--commit`` tells the script to actually delete the files.  By default, the
script runs in dryrun mode, where no files are deleted.  Running in dryrun mode
is only useful for sanity checking the script arguments and/or testing the
script behaviour.

The target directory tree is a mandatory positional argument.


Other use cases
================
While this this script *can* be used to delete any file from any directory tree
based on filename patterns and age, it is only intended for cleaning up
old, failed temporary files from the atomicfile writers.

See :doc:`file-cleaner` for a more generic utility for deleting old files.
