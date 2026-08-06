===================
System maintenance
===================

There are a couple of jobs that should *always* run in a Cerebrum deployment.


File cleanup
=============
Cerebrum produces various output files, both temporary and otherwise.  As a
deployment grows and changes, some files will typically be left behind and need
cleanup.

See :doc:`file-cleanup` for more details on this subject.


Data cleanup
=============
Parts of the database typically needs periodic cleanup.

TODO: Document clean up jobs.


Documents
=========

.. toctree::
   :maxdepth: 1
   :glob:

   *
