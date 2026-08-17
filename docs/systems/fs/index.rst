===
FS
===

Felles studentsystem (FS) is a student information system (SIS), and is the
source system for students in Cerebrum.

.. todo::
   This document needs some work.  It is mainly provided as an index and
   overview for the legacy *autostud* documentation.


FS Import
==========
Most of the FS integration consists of the FS *import*.  This process is split
into the following steps:

Database lookups
    The first step of the FS import is to fetch data directly from FS:

    - This is done by individual ``contrib/no/*/import_from_fs.py`` scripts

    - The script connects directly to the FS database, using the appropriate FS client
      implementation in Cerebrum (``Cerebrum.modules.no.access_FS.make_db``)

    - The script looks up batches of information (students, courses, etc..)

    - Each batch is written to an *XML file*.

Post-processing
    XML files with person data and roles are typically *merged* using
    ``contrib/no/merge_xml_files.py``.

Identifier import
    Person merges and other id fixups are processed using
    ``contrib/no/fnr_update.py``.  This ensures that IDs from the XML files
    links to the correct person object in Cerebrum.

Main import
    The XML files are read, and compared to the current Cerebrum state.

    This is typically done using individual ``contrib/no/*/import_FS.py``
    scripts.


FS Export
==========
As part of the FS integration, we may update FS with personal details from
Cerebrum.

Username and email
    The ``contrib/no/update_FS_mailadr.py`` script will update FS with usernames
    and/or email addresses from Cerebrum.

Add employees
    The ``contrib/no/hr2fs-person.py`` script adds employees and employee data
    to FS.


Student processing
===================
.. toctree::
   :maxdepth: 1
   :glob:

   autostud/*

The student processing module is closely related to the FS import.  It typically
runs immediately after the FS-import, and builds user accounts for active
students.

Note that the processing scripts also depends on the FS XML files, as it
requires some data that is too simplified in Cerebrum, or not imported at all.
