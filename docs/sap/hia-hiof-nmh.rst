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


SAP data files exchanged between Cerebrum and SAP
==================================================

File format
------------
All files share the same CSV-like format.  Each line is a single record, and
each record is consist of fields separated by semicolons (;).

If a semicolon occurs within a field, it's escaped by "\" (backslash).  How
backslashes are escaped has never been specified, but will presumably follow
standard CSV rules for escaping.

. The parsing happens by splitting and post-processing each line with ``re``
(``mod_sap_utils.py``), but we may want to consider using the ``csv`` python
module. The files are in ISO-8859-1, but this encoding has never actually been
agreed upon.


File: ``feide_forromr.txt``
----------------------------
A list of valid geographical codes (Norwegian: forretningsområdekoder).
Geographical codes are used to identify organizational units.  This file
is *not* imported every night.  It is used at deployment time to register the
constants representing the geographical codes.

TODO: Clarify what this means (register constants?)


File: ``feide_orgenh.txt``
----------------------------
A list of organizational units known to SAP.  Currently this file is *not*
used, as FS is the authoritative source for organizational structure for the
organizations that use this import.

However, this file *could* be used as a source of org units and org tree data,
or to check if OUs known to SAP are also known to FS.

Fields:

#. OU id (internal SAP id).  A magic, non-unique number which identifies OUs
   uniquely together with the geographical code.
#. OU name.
#. Unused and ignored (Norwegian description: nummer på kostnadssted).
#. Unused and ignored (Norwegian description: navn på kostnadssted).
#. Geographical code.  This number must occur in ``feide_forromr.txt``
#. OU short name.
#. Parent OU id.  Note taht there is an implicit assumption that the child and
   the parent share the same geographical code. Since FS is the authoritative
   source with regard to OU structure, the parent id irrelevant to Cerebrum.

Example:
::

      10000054;Stab Ledelsen;0000000014;Studiesekretariat;0011;Stab led;10000053

Note that the SAP OU id must be registered in FS (``fs.sted.stedkode_konv``).
This column must be used to populate an external ID in Cerebrum, which again can
be used when pairing e.g. ou data, roles, or other OU references in SAP data.


File: ``feide_persondata.txt``
----------------------------------
A list of all employees known to SAP.  The file contains names, ids, birth
dates, addresses and so on.  This file is imported nightly and the information
in Cerebrum is updated with its content.

The import creates persons and and updates personal data from this file.

The file has **37** fields, where the ones important to Cerebrum are (counted
from 0):

- *0*: Id - SAP employee number
- *3*: Name - Initials
- *4*: Id - Norwegian national ID number (fnr)
- *5*: Birthdate
- *6*: Name - First name
- *7*: Name - Middle name
- *8*: Name - Surname
- *12*: Contact - Private phone number
- *13*: Contact - Contact phone
- *14*: Contact - Contact cellular phone
- *18*: Address - C/O field
- *19*: Address - Street field
- *20*: Address - House number field
- *21*: Address - Extra address field
- *22*: Address - City field
- *23*: Address - Zip code field
- *24*: Address - Country field
- *25*: Geographical code (forretningsområdekode)
- *25*: Contact - Private cellular phone
- *28*: Work title
- *33*: Death status
- *36*: Publishable flag (whether the person can be published in
        electronic catalogs (e.g. LDAP))

Any of the fields may be empty in the report, but the import itself will require
certain fields to be present.

"Death status" is used for two purposes -- marking deceased people (by the
keyword "Død"), and marking retired people. How retirees are marked is yet to be
determined. 

Since SAP offers no interface to track ID changes (employee# and fnr), there is
no direct way to figure out when a person's fnr changes.  Even worse, despite
the promise that employee number would have a 1-to-1 correspondance with people,
there have been incidents of people having multiple employee numbers.  In order to
(partially) remedy the situation, the import script checks that the (employee
number, fnr) *pair* in the file matches the corresponding *pair* in Cerebrum.


File: ``feide_persti.txt``
------------------------------
A list of all employments known to SAP.  Only the valid employments (more on
this later) will grant employee (ANSATT) affiliations.

The import assigns affiliations from this file, given that the employee and
employments are valid according to our rules.

The file has 9 fields:
::

      12345678;10000102;30000892;20001008;0032;20031101;99991231;H;70.00

… which are:

- SAP employee number
- SAP OU number
- Personal employment code (SAP.PLANS)
- Employment code (SAP.STELL). This is the one actually being used.
- Geographical code (forretningsområdekode).
- Start date
- End date
- Employment kind (H = Hovedstilling, B = Bistilling)
- Percentage of the employment (0-100).

A note on start/end dates:  Although initially just that, turned out to be used
for more than simply employment interval designation.  In several cases at HiA
an employee resigning from a position is registered with a "new" employment,
where the start date is actually the end date for the current employment.

This "inversion" of the field meaning is presently (2007-04-13) not handled in
any adequate fashion.

Since new employment codes appear every now and then, it is important to check
the employment code (SAP.STELL) validity before importing the records into
Cerebrum.

This file is used primary to figure out who the active employees are and to
assign them ANSATT and TILKNYTTET affiliations.


File: ``feide_stilltype.txt``
--------------------------------
A list of employment codes (SAP.STELL) and the mapping between SAP
employment codes and the 4-digit Norwegian government employment codes.

There has been a bit of confusion regarding the Norwegian name for SAP
codes, since "stillingskode" and "stillingstype" have both been used. The
problem is that there is a different *personal* employment code (SAP.PLANS),
listed in the file ``feide_stillkode.txt``. Although this file has been
largely ignored, its codes appear in ``feide_persti.txt``.

The employment codes are not imported on a daily basis. Rather, the file
is used during the setup stage to register the proper constants for SAP,
much like ``feide_forromr.txt``.


File: ``feide_utvalg.txt``
------------------------------
A list of registed committees (Norwegian: utvalg) in use at each institution.
This file, much like ``feide_forromr.txt`` is used only once during the setup
stage to populate Cerebrum with the proper constants.


File: ``feide_perutvalg.txt``
---------------------------------
A list of committee roles (i.e. participation in committees) - companion file to
the committee definition file ``feide_utvalg.txt``.

Each file has a fixed number of fields per line. The number of fields varies
from file to file.

The meaning of the fields is based on the original specification handed to
Cerebrum by UiA (HiA at the time):


The original specification has been e-mailed to Cerebrum by HiA. NMH and HiØf
are using the same implementation and therefore the same format. The
specification is available `online
<http://www.hia.no/it/prosjekt/feide/SAP-eksport-HiA.htm>`_.


Special values
---------------
Certain values (esp. in code fields) have special meaning in the SAP files and
records with these values should be treated differently from all other
records.

Geographical code (forretningsområdekode)
    The value *9999* means that the entire record should be ignored. This code
    is typically used to tag invalid/irrelevant entries.

    This applies to all files where this field is present.


Publishable flag
    Field number 36 (when counting from 0) in ``feide_person.txt`` indicates if
    a person can be published in catalogs (e.g. LDAP).  The field can have the
    following values:

    - ``""`` (empty string) means that the person can be published in
      electronic catalogs.

    - "Kan publiseres" means that the person can be published in electronic
      catalogs.

    - *All* other values mean no publication in electronic catalogs is allowed.

Employment code (``SAP.STELL``)
    Field number 3 (when counting from 0) in ``feide_persti.txt`` is the
    employment code we actually use for employees.

    The value ``"20009999"`` should result in assigning the person
    ``TILKNYTTET/ekstern`` affiliation.  All other values should map to an
    ``ANSATT`` affiliation.

Personal employment code (``SAP.PLANS``)
    Field number 2 (when counting from 0) in ``feide_persti.txt`` is not used by
    Cerebrum.

    The value ``"99999999"`` in this field  *probably* means that the employment
    entry has expired.  Perhaps surprisingly, the "end date" field is NOT
    (always?) used for this purpose.  This is a conjecture based on the
    interpretation of a few examples we have been shown, and has never been
    specified.

    For the time being (2007-04-16) this field is ignored, pending FSI's
    decision regarding future support of this file format.

    FIXME! One of the tables in mod_sap encompasses this field as a primary key.
    **Why**?


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
