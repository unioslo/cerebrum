===================
System maintenance
===================

There are a couple of jobs that should *always* run in a Cerebrum deployment.


File cleanup
=============
Cerebrum produces various output directories and files, usually in the form of
export files, logs, or temporary caches/work.  As a deployment grows and
changes, some files will typically be left behind and need cleanup.

In other words, these files and directories needs some sort of lifecycle
management to prevent them for cluttering up the file system.

Cerebrum includes some utilities to deal with this problem:

- :doc:`job-runner` for temporary workdirs
- :doc:`failed-exports` for failed exports

In addition, :doc:`file-cleaner` can be configured to archive and/or delete all
sorts of files and directories.


Data cleanup
=============
Parts of the database typically needs periodic cleanup.

.. todo:: Document cleanup jobs.


Documents
=========

.. toctree::
   :maxdepth: 1
   :glob:

   *
