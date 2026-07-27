====================================
SAP details for HiA, HiØf and NMH
====================================

.. admonition:: Needs review

   This is an old document, some of the instructions may be out of date.

.. contents:: Table of contentt ss
.. section-numbering::


Introduction
=============
This document describes data processing for the SAP-originated data at
Universitetet i Agder (UiA), and Norges Musikkhøyskole (NMH). The main goal is
to provide an overall description of the data exchanged, the jobs involved, and
the nitty-gritty details.

These institutions all use the same data format from SAP, and they are therefore
treated as one.  Any local differences will be pointed out later.


Overall dataflow description
=============================
The overall data flow is sketched in the figure below:
::


  +-----+   1    +------+    2     +-----+    3      +----+
  | sap | -----> | inst | -------> | crb | --------> | db |
  +-----+        +------+  rsync   +-----+  import   +----+

1. Import files are moved onto a host at the host institution.  This task is
   outside the scope of Cerebrum, and left to the institution to solve.

2. The import files are rsynced to the Cerebrum host for the institution.  This
   is typically defined by a daily/nightly rsync action in the ``scheduled_jobs`` module.
   The files are typically placed under ``/cerebrum/var/cache/SAP/``.

3. The cerebrum import jobs process the up-to-date import files, and updates the
   database.

Currently, one institution only exports data back to SAP -- UiA. The generated
data file travels along the same path ¿ i.e. the file is written to
``/cerebrum/var/cache/SAP/`` and then rsynced back to the sync host at UiA.
Whatever happens after that is none of Cerebrum's concern.


Cerebrum modules
=================
Cerebrum core db schema does not capture all the information contained in the
SAP data files.  Therefore, a special module has been designed for this purpose
-- ``mod_sap.sql``.  Any installation wishing to use SAP solution akin to
HiA/HiØf/NMH should load this schema when creating the database.

The module consist of:

``design/mod_sap.sql``
    The schema itself is located in file ``mod_sap.sql``.


``Cerebrum.modules.no.Constants``
    Defines two new SAP-related constant types - employment codes and employment
    types.

    Employment types (``SAPStillingsTypeKode``) is not in use.  Employment codes
    (``SAPLonnsTittelKode``) are used to map employments in SAP to affiliations
    in Cerebrum.

``Cerebrum.modules.no.mod_sap_codes.SAPConstants``
    Adds a series of common employment codes to Cerebrum.  Each institution may
    define additional employment codes.


Import
======
Note that the import was originally implemented for UiA, and then later used by
NIH, NMH.  Some obsolete environments also used this import.

The main purpose of the import is to read and update Cerebrum from:

- ``feide_persondata.txt`` with employee data
- ``feide_persti.txt`` with employee roles


Steps:

#. Sync files (typically rsync from an ssh host)
#. ``contrib/no/hia/import_SAP_OU_id.py`` - update org units with SAP ids
#. ``contrib/no/hia/import_SAP_person.py`` - import employee data
#. ``contrib/no/hia/process_SAP_affiliations.py`` - import employee roles


OU import
---------

Example:
::

    python contrib/no/hia/import_SAP_OU_id.py --ou-file system_fs:ou.xml

Note that this import reads the regular ``ou.xml`` file fetched from FS.  At no
point are org units from DFØ actually processed.

It's not clear why this isn't handled by the common ou-import.  At some point it
was decided to write a separate script to process the same file, and update org
units with the SAP IDs.


Employee import
----------------

Example:
::

    python contrib/no/hia/import_SAP_person.py \\
        --without-fok \\
        --person-file feide_persondata.txt \\
        --passnr-file MD2_Persondata_status.csv


Reads the ``feide_persondata.txt`` csv file and imports employee data:

- If fok (forretningsområdekode) is used, any employee with ``fok = 9999`` is
  ignored

- Any employee with an ``endDate`` in the past is ignored

- Find existing employee by fnr + sap-id.

  - If not found - create a new person
  - If found by sap-id - update fnr and use person
  - If found by fnr - use person

- Update employee data: gender, date of birth, external ids
- Update employee data: names, contact info, address, titles, "hidden" group membership


Note that using a ``--passnr-file`` is optional, and adds support for PASSNR in
addition to fnr (NO_BIRTHNO).


Employment import
-----------------

Example:
::

    python contrib/no/hia/process_SAP_affiliations.py \\
        -e feide_persti.txt \\
        -p feide_persondata.txt \\
        --with-employment \\
        --without-fok


In short, this script will process the ``feide_persti.txt`` file and map
employment roles to affiliations in Cerebrum.  Any valid role is added as an
affiliation, and old affiliations in Cerebrum are removed.

At first, the script builds a cache of employees from the
``feide_persondata.txt`` file.  The ``--without-fok`` flag has the same effect
here as in the `employee import`_ - i.e. ignores selected employments.

Then the script builds a cache of employments - this step ignores any employment
where:

- The org unit cannot be found in Cerebrum
- The employee cannot be found in Cerebrum
- The employment should be ignored (e.g. a given fok)
- The employment is in the past (endDate)

The employments are then translated and processed. The employment code
(``SAP.STELL``) is mapped to an affiliation according to the employment codes
(``mod_sap_codes``) present in Cerebrum.  The resulting affiliation is then
added or updated.

If the ``--with-employment`` flag is used, employment data is also added to the
``mod_employment`` module.

Finally, any remaining active affiliation that *didn't* get updated by the
import will be removed.
