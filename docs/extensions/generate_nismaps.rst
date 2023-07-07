=====================================
 Cerebrum extension generate_nismaps
=====================================


What does the generate_nismaps extension do?
============================================

It dumps Cerebrum data in text file formats suitable for building the
``passwd``, ``group`` and ``netgroup.user`` NIS maps.  Groups and
users to be included in the dump are selected by spreads.


Configuration variables specific to this extension
==================================================

None.


Usage
=====
.. TODO: Extract usage string from usage function in script.

Example::

 generate_nismaps.py --user_spread NIS_user@uio --group_spread NIS_fg@uio --passwd /var/yp/src/passwd


Detailed description
=====================
.. TODO: Extract module docstring from script.

All output is written to temporary files which must pass sanity
checking before being renamed to the file name given on the command
line.  One such sanity test is that the size of the file must not
change too much between two consecutive runs.

When generating ``group`` output
--------------------------------

This extension will flatten groups with subgroup members.

Group names must pass the ``Factory-Group.illegal_name()`` test.

When generating ``netgroup.user`` output
----------------------------------------

Subgroup members that does not have the appropriate spread for export
will be flattened into the nearest parent group possessing this
spread.

The extension does not yet handle ``intersection`` or ``difference``
group members for netgroups.

When generating ``passwd`` output
---------------------------------

User names must pass the ``Factory-Account.illegal_name()`` test.


Related extensions
------------------

* `PosixUser <PosixEntity.html#PosixUser>`_
* `PosixGroup <PosixEntity.html#PosixGroup>`_

Files
-----
.. TODO: Legge inn markup for å indikere at linjen under faktisk er et
         filnavn.

contrib/generate_nismaps.py

..
