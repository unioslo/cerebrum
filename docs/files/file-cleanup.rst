=============
File cleanup
=============
Parts of Cerebrum produce output files, logs, or entire directory trees.
These files and directories needs some sort of lifecycle management to
prevent them for cluttering up the file system.

This document describes the various mechanisms that exists for managing
these files.

.. contents::

.. section-numbering::


job-runner
==========
The Cerebrum scheduler, ``job-runner``, creates a new workdir for each
job/process it starts.  In addition to being the workdir for processes started
by the job, output to stdout or stderr is written to their own respective file
in this directory.

The directory is normally deleted after the job completes, but is *archived*
(renamed and kept indefinitely) if the job fails for any reason.


Deleting old workdirs
----------------------
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


File exports
=============
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
-------------------------
Just as with `job-runner`_, keeping these files around will cause problems in
the long run, so we have a utility script for dealing with them.

The cleanup script, ``contrib/utils/delete-temp-files.py``, will recursively
search a given directory tree for files with a given glob-like pattern, and
delete them after some time.  As with other file cleanup scripts, this should be
added as a job-runner job.

The job should run something like:
::

    python contrib/utils/delete-temp-files.py \
        --logger-name cronjob \
        --logger-level INFO \
        --min-age 7
        --glob-pattern *.json.?????
        --glob-pattern *.ldif.?????
        --glob-pattern *.pickle.?????
        --glob-pattern *.xml.?????
        --commit
        /cerebrum/var/cache/

``--glob-pattern`` adds a filename pattern to delete.  Temporary files created
by atomicfile will use the same name as the *target file*, but with a randomized
five-letter suffix/extension.

``--min-age`` is used to specify how many days the mathcing files should be kept
around before being deleted.  The file *mtime* is used to decide its age.
Note that a minimum age should always be provided.  If omitted or set to ``0``,
you risk removing a temporary file that is currently being written.

``--commit`` tells the script to actually delete the files.  By default, the
script runs in dryrun mode, where no files are deleted.  Running in dryrun mode
is only useful for sanity checking the script arguments and/or testing the
script behaviour.

The target directory tree is a mandatory positional argument.

While this this script *can* be used to delete any file from any directory tree
based on filename patterns and age, it is only intended for cleaning up
old, failed temporary files from the atomicfile writers.  See `file-cleaner`_
for a more generic utility for deleting old files.


Archiving and deleting old files
=================================
The other utility scripts described in this document deals with specific files
and directories from specific Cerebrum components.

All other Cerebrum file cleanup needs should be handled by *file-cleaner*.

file-cleaner
------------
The utility script ``cerebrum/utils/file-cleaner.py`` reads a series of archive
or delete instructions from a config file.

By default, the config is read from an importable Python module, ``file_clean_conf``, but any
importable or non-importable Python module/file can be used.

You would typically write a ``file_clean_conf`` module and specify a job in
job-runner to run this job once per day.  A typical invocation would look
something like:
::

    python contrib/utils/file-cleaner.py \
        --logger-name cronjob \
        --logger-level INFO \
        --archive
        --delete
        --commit

``--archive`` instructs the script to run the archive instructions from the
config, and ``--delete`` does the same for delete instructions.

``--commit`` tells the script to actually create and delete files and
directories.  By default the script runs in dryrun mode, which only logs any
actions it *would* take.  Running in dryrun mode is only useful for sanity
checking the config and/or testing the script behaviour.


Modes of operation
~~~~~~~~~~~~~~~~~~~
The different combinations of settings can be distilled down to a couple of
*modes*:

Delete file or directory
    Delete all matching files or directories.

Compress file
    Replace each matching file with a gzip-compressed copy.

    The gzipped file keeps the attribtues (permissions, mtime, etc...) from the
    original.  Archived files are named ``<source-file>.gz`` (or
    ``<source-file>--<counter>.gz`` for duplicate names).

Compress directory
    Replace each matching directory with a gzip-compressed tarball.

    The gzipped directory keeps the timestamp (mtime) of the the source
    directory.  Archives are named ``<source-directory>.tar.gz`` (or
    ``<source-directory>--<counter>.tar.gz`` for duplicate names).

Create a *combined archive*
    Combine *all* matching entries (file or directory) into a single
    gzip-compressed tarball.

    The *mtime* of the archive is set to the current date, and the archive
    *mtime* is not manipulated.  Archives are named
    ``<archive-combo>-<date>.tar.gz`` (or potentially
    ``<archive-combo>-<date>--<counter>.tar.gz`` for duplicate names).



Config
~~~~~~~
The config file is a Python module with two attributes, ``ARCHIVE_FILES`` and
``DELETE_FILES``.  Both attributes are lists of instructions, and each
instruction entry is a dictionary with settings.

The following settings apply to both ``ARCHIVE_FILES`` and ``DELETE_FILES``
instructions:

``dirname``
    Directory with files or subdirectories to either delete or archive.

    This value has no default and is always required.

    The script doesn't search *recursively* for the given *pattern* - it only
    matches files or directories in *dirname*.  However, when archiving or
    deleting *directories*, the entire directory is archived and/or deleted.

``file_type``
    Either "file" or "dir".  Will only match entries in *dirname* of this type.

    This value has no default and is always required.

``pattern``
    This is a regex pattern for selecting files or directories within *dirname*
    to archive or delete.

    This value has no default and is always required.

    Take care to not use a pattern that matches your *archived* files when no
    separate *archive_dir* is given.  It is generally good practive to include a
    trailing ``$`` to prevent matching unintended files or directories.

``delete_age``
    How many days to keep files (when deleting) or archives (when archiving)
    before they are deleted.

    This value has no default and is always required.  It behaves differently in
    delete and archive instructions:

    - when deleting, this specifies how old matching entries should be before
      they are deleted.  A ``0`` value will cause all matching name patterns to
      be deleted regadless of age.

    - when archiving, this specifies how old the archived copy should be before
      it's deleted.  A ``0`` value will prevent archive cleanup!


The following settings only apply to ``ARCHIVE_FILES`` instructions:

``archive_age``
    Number of days to wait before archiving matching files or directories - only
    entries that are at least *archive_age* days old will be archived.

    This value has no default and is always required.  The value ``0`` will
    archive all matching entries regardless of age.

``archive_dir``
    An alternative directory to place archives in.  The default (``None``) will
    use *dirname* as the archive directory.

``keep_originals``
    Set to ``True`` to keep the input files after they have been archived.

    The default (``False``) will delete input entries, and only keep the
    archived copy.

    If this is set to ``True``, future runs will end up archiving the same file
    or directory again unless something else removes or renames it.  This is
    typically used in combination with ``archive_combo`` to create archives or
    backups of e.g. incoming files, which should always be available.

``archive_combo``
    Name prefix for a *combined archive*.

    If this is set, all matching entries in *dirname* will be placed in a
    single archive file.  The default (``None``) will create one archive for
    each matching entry.

``archive_replace``
    Replace archive files if if they already exists.

    The naming scheme for archives may cause a naming conflict.  This can happen
    if the cleanup script runs multiple times a day, and/or the
    ``keep_originals`` setting is enabled.

    If set to ``True``, the new archive will replace the exising archive in
    these cases.

    If set to ``False`` (the default), archive filenames gets an additional
    counter suffix to resolve naming conflicts.


Typical use-cases
------------------
Compressing logs
    Logs from Cerebrum are typically not compressed, which can cause the
    filesystem to fill up from overly active scripts and daemons.

    This can be fixed by adding log compression and log retention to
    file-cleaner.  A typical setup looks something like this:

    1. A script or daemon logs to a file that includes the script startup date,
       or uses a TimedRotatingFileHandler to rotate files daily.

    2. An entry is added to the ``file_clean_conf`` with the log directory and log filename
       pattern to compress these logs.

    The following example includes a typical config for the API daemon.  Logs
    are compressed in-place (i.e. the compressed copy is placed in the same
    directory as the uncompressed log, and the uncompressed log is deleted after
    compression is complete).

    We wait a couple of days before compressing the log files - this should
    help to prevent race conditions if the logs are being rotated while we are
    compressing them.  Additionally we don't need to use ``zgrep`` or similar
    tools to search the most recent logs.

    Logs are kept for 180 days before being deleted.

    The config would look something like this:
    ::

        ARCHIVE_FILES = [
            {
                'dirname': "/cerebrum/var/log/api/"
                'file_type': "file",
                'pattern': r"log-\d+-\d+-\d+$",
                'archive_age': 7,
                'delete_age': 180,
            },
            ...
        ]


Creating daily backups of input/output files
    It can be useful to keep a copy of import or export files e.g. to quickly
    revert to a known working state in case of errors, or to debug.

    In this case, we would typically create a daily archive, while *not*
    deleting the originals, as the current state should always be available.
    Note that the archives are placed in their own subdirectory.

    The config would look something like this:
    ::

        ARCHIVE_FILES = [
            {
                'dirname': "/cerebrum/var/cache/SAP/",
                'file_type': "file",
                'pattern': r"(?:feide_\w+\.txt|MD2_\w+\.csv)$",
                'archive_dir': "/cerebrum/var/cache/SAP/archive/",
                'archive_combo': "sap-import",
                'archive_replace': True,
                'keep_originals': True,
                'archive_age': 0,
                'delete_age': 7,
            },
        ]


Deleting obsolete files
    While some files and directories have their own, dedicated clean up scripts
    (see `job-runner`_ and `file exports`_), ``file-cleaner`` can be used to
    remove files and directories based on age and naming patterns.

    One useful use case is to remove old *letters* that have been rendered using
    ``bofhd``.  The config for that would look something like:
    ::

        DELETE_FILES = [
            {
                'dirname': "/path/to/letter-cache/",
                'file_type': "dir",
                'pattern': r"bofh_spool_\d+\.[A-Za-z0-9]+$",
                'delete_age': 3,
            },
            ...
        ]

