====================================
SAP data files from DFØ to Cerebrum
====================================

.. admonition:: Needs review

   This is a rewritten, old document. Some information may be slightly out of date.


.. contents::
.. section-numbering::


File format
============
All files share the same CSV-like format.  Each line is a single record, and
each record is consist of fields separated by semicolons (;).

If a semicolon occurs within a field, it's escaped by "\" (backslash).  How
backslashes are escaped has never been specified, but will presumably follow
standard CSV rules for escaping.

The parsing happens by splitting and post-processing each line with ``re``
(``mod_sap_utils.py``), but we may want to consider using the ``csv`` python
module. The files are in ISO-8859-1, but this encoding has never actually been
agreed upon.

The original specification has been e-mailed to Cerebrum by HiA.  NMH and HiØ
are using the same implementation and therefore the same format.  The
specification was available online at
`<http://www.hia.no/it/prosjekt/feide/SAP-eksport-HiA.htm>`_, and has been
indexed by `<https://web.archive.org/>`_.  This format seems to have been
standardized, and are used by most DFØ customers.


Files
=====

.. admonition:: Incomplete

   This list is not complete.  More files have been added to the integration
   later, most notably the ``MD2_Persondata_status.csv`` from UiA.

   Also, some of the files may have served a purpose, but are no longer in use
   by the import.


feide_forromr.txt
-----------------
A list of valid geographical codes (Norwegian: forretningsområdekoder).  This
file *is not used* by Cerebrum.

Geographical codes are used to identify organizational units, and each SAP OU id
belongs to a geographical code.  Both the geographical code and ou id is needed
to uniquely identify an org unit.

The code is typically *also* present in FS (as a part of
``fs.sted.stedkode_konv``).

Fields:

#. code - a four digit code
#. name - a name or description of the code (up to 40 chars)


Example:
::

    0001;Some location
    9999;Some other location


feide_fravtx.txt
----------------
Definitions of various types of leave-of-absence.  This file *is not used* by
Cerebrum.

Fields:

#. type - a four digit code
#. description - a description (up to 25 chars)

Example:
::

    0001;Present
    0002;Paid vacation
    0003;Field work


feide_orgenh.txt
----------------
A list of organizational units known to SAP.  This file *is not used* by
Cerebrum by any integration, as FS is the authoritative source for
organizational structure for the organizations that use this import.

However, this file *could* be used as a source of org units and org tree data,
or to sanity check if OUs known to SAP are also known to FS.

Fields:

#. OU id (internal SAP id) - a (potentially non-unique) 8 digit number.  Will uniquely
   identify the org-unit if combined with the geographical code.
#. OU name - (up to 40 chars)
#. Cost location id - unused and ignored (Norwegian description: nummer på kostnadssted).
#. Cost location name - (Norwegian description: navn på kostnadssted).
#. Geographical code - A code from the `feide_forromr.txt`_
#. OU short name - (up to 10 chars)
#. Parent OU id - Note that there is an implicit assumption that the child and
   the parent share the same geographical code.

Example:
::

      10000054;Stab Ledelsen;0000000014;Studiesekretariat;0011;Stab led;10000053

Note that the SAP OU id must be registered in FS (``fs.sted.stedkode_konv``).
This column must be used to populate an external ID in Cerebrum, which again can
be used when pairing e.g. ou data, roles, or other OU references in SAP data.


feide_persondata.txt
--------------------
A list of all employees known to SAP.  This file *is used* by Cerebrum.  It
contains names, ids, birth dates, addresses and so on.

The import creates persons and and updates personal data from this file.  The
file has **37** fields, where the ones important to Cerebrum are (counted
from 0).

- *0*: Id - SAP employee number
- *2*: Employment end date (YYYYMMDD)
- *3*: Name - Initials
- *4*: Id - Norwegian national ID number (fnr)
- *5*: Birthdate (YYYYMMDD)
- *6*: Name - First name
- *7*: Name - Middle name
- *8*: Name - Surname
- *11*: Employment - Primary location (an ou id from `feide_orgenh.txt`_)
- *12*: Contact - Private phone number
- *13*: Contact - Work phone number
- *14*: Contact - Work cellular phone number
- *15*: Contact - Private cellular phone number
- *16*: Contact - Work email address
- *17*: Contact - Private email address
- *18*: Address - C/O field
- *19*: Address - Street field
- *20*: Address - House number field
- *21*: Address - Extra address field
- *22*: Address - City field
- *23*: Address - Zip code field
- *24*: Address - Country field (3 chars)
- *25*: Employment - Primary location (a geographical code from
  `feide_forromr.txt`_)
- *26*: Building number
- *27*: Room number
- *28*: Personal title
- *29*: Contact - Fax number
- *30*: Preferred language (2 chars)
- *31*: Employment - Start date (YYYYMMDD)
- *32*: Employment - End date (YYYYMMDD)
- *33*: Death status
- *34*: Absence code - a code from `feide_fravtx.txt`_)
- *35*: Absence fraction - a percentage, 0-100
- *36*: Publishable flag (whether the person can be published in
        electronic catalogs (e.g. LDAP))
- *37*: Employee group (MG - Norwegian: medarbeidergruppe)
- *38*: Employee subgroup (MUG - Norwegian: medarbeiderundergruppe)


Any of the fields may be empty in the report, but the import itself will require
certain fields to be present.  Most fields aren't actually used by the import,
and employment data is mostly fetched from `feide_persti.txt`_ and ignored in
this file.

"Death status" is used for two purposes -- marking deceased people (by the
keyword "Død"), and marking retired people.  How retirees are marked is yet to be
determined.

Since SAP offers no interface to track ID changes (employee# and fnr), there is
no direct way to figure out when a person's fnr changes.  Even worse, despite
the promise that employee number would have a 1-to-1 correspondance with people,
there have been incidents of people having multiple employee numbers.  In order to
(partially) remedy the situation, the import script checks that the (employee
number, fnr) *pair* in the file matches the corresponding *pair* in Cerebrum.


feide_persti.txt
----------------
A list of all employments known to SAP.  This file *is used* by Cerebrum.

It defines which valid employments (more on this later) will grant employee
(ANSATT) affiliations.

The file has 9 fields:
::

      12345678;10000102;30000892;20001008;0032;20031101;99991231;H;70.00

… which are:

#. SAP employee number - used to correlate with `feide_persondata.txt`_
#. SAP OU id
#. Employment id - (SAP.PLANS)
#. Employment code (SAP.STELL). This is the one actually being used.
#. Geographical code
#. Start date (YYYYMMDD)
#. End date (YYYYMMDD)
#. Employment kind - H = hovedstilling (main assignment), B = Bistilling
   (secondary assignment)
#. Employment percentage - 0-100

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


feide_stillkode.txt
-------------------
A list of employment ids (assignment ids, Norwegian: stillingsid).  This file
*is not used* by Cerebrum.

This file lists all employments, along with a employee title:

#. Employment id - this is the same id as in `feide_persti.txt_`
#. Title - This is an employee title (e.g. professor, reasearcher)

The title seems to be a *preferred* title - i.e. a *personal title* if one is
assigned, or the assignment title if no personal title is given.


feide_stilltype.txt
-------------------
A list of employment codes (SAP.STELL) and the mapping between SAP
employment codes and the 4-digit Norwegian government employment codes.
This file *is not used* by Cerebrum, but will typically be duplicated in
Cerebrum as a ``mod_sap_codes`` module of ``SAPLonnsTittelKode`` constants.

There has been a bit of confusion regarding the Norwegian name for SAP
codes, since "stillingskode" and "stillingstype" have both been used. The
problem is that there is a different *personal* employment code (SAP.PLANS),
listed in the file `feide_stillkode.txt`_. Although this file has been
largely ignored, its codes appear in `feide_persti.txt`_.

The employment codes are not imported on a daily basis. Rather, the file
is used during the setup stage to register the proper constants for SAP,
much like `feide_forromr.txt`_.


feide_utvalg.txt
----------------
A list of registed role types or *groups* (Norwegian: utvalg) in use at each
institution.  This file *is not used* by Cerebrum.

The *groups* can typically be:

- A committee (verv)
- A permission (e.g. ephorte)
- or some other tag/label to group employees

The file contains a list of definitnions for use by `feide_perutvalg.txt`_,
with fields:

#. code - a four digit identifier
#. name - a name/description


feide_perutvalg.txt
-------------------
A list of roles (i.e. group memberships) - companion file to the group
definition file `feide_utvalg.txt`_.  This file *is not used* by Cerebrum.

Fields:

#. SAP employee number - used to correlate with `feide_persondata.txt`_
#. SAP OU id
#. Geographical code
#. Name - a name from the `feide_utvalg.txt`_
#. Start date (YYYYMMDD)
#. End date (YYYYMMDD)
#. An optional group role



Special values
===============
Certain values (esp. in code fields) have special meaning in the SAP files and
records with these values should be treated differently from all other
records.

Geographical code (forretningsområdekode)
    In some integrations, the value *9999* means that the entire record should
    be ignored. This code is typically used to tag invalid/irrelevant entries.

    This applies to all files where this field is present.

Publishable flag
    Field number 36 (when counting from 0) in ``feide_person.txt`` indicates if
    a person can be published in catalogs (e.g. LDAP).  The field can have the
    following values:

    - ``""`` (empty string) means that the person can be published in
      electronic catalogs.

    - ``"Kan publiseres"`` means that the person can be published in electronic
      catalogs.

    - *All* other values mean no publication in electronic catalogs is allowed.

Employment code (``SAP.STELL``)
    Field number 3 (when counting from 0) in ``feide_persti.txt`` is the
    employment code we actually use for employees.

    The value ``"20009999"`` should result in assigning the person
    ``TILKNYTTET/ekstern`` affiliation.  All other values should map to an
    ``ANSATT`` affiliation.

Personal employment code (``SAP.PLANS``)
    Field number 2 (when counting from 0) in `feide_persti.txt`_ is not used by
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
