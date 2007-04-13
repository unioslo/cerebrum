==================================
SAP details for HiA, HiØf and NMH
==================================

.. contents:: Table of contents
.. section-numbering::


Introduction
=============

This document describes data processing for the SAP-originated data at
Høyskolen i Agder (HiA), Høyskolen i Østfold (HiØf) and Norges
musikkhøyskole. The main goal is to provide an overall description of the data
exchanged, the jobs involved and the nitty-gritty details.

These three institutions all use the same data format from SAP, and they are
therefore treated as one. The differences will be pointed out, if the need
should arise.


Overall dataflow description
=============================

Today, 2007-04-06, the overall data flow is sketched in the figure below: ::


  +-----+  files   +-----+  rsync of +-----+ import   +--------+
  | sap | -------> |     | --------> |     | -------> |cerebrum|
  +-----+          +-----+ the files +-----+    jobs  |   db   |
                 institution        cereprod-A        +--------+
                    server

``cereprod-A`` and ``cerebrum db`` can very well be the same physical
host. How each institution obtains their respective data files is of no
concern to Cerebrum. Cerebrum simply expects the latest data files to be
obtainable from a given institution server once a day (usually during the
night, when most of the daily (nightly?) jobs are running).

The files are rsync'ed to ``/cerebrum/dumps/SAP/`` (naturally, any other
location is possible. This is just a tradition). The import jobs process the
files in certain order and populate various tables in Cerebrum. Once the
imports are complete, the updated SAP information (names, affiliations,
employments, etc.) is available via the usual Cerebrum API (provided that the
proper mixins have been configured in ``cereconf.py``).

Currently, one institution only exports data back to SAP -- HiA. The generated
data file travels along the same path. I.e. the file is written to
``/cerebrum/dumps/SAP/`` and then rsync'ed over to the institution server.
Whatever happens after that is none of Cerebrum's concern.


Data files exchange between Cerebrum and SAP
=============================================

These are the files that are automatically fetched every night:

  * ``feide_forromr.txt``. A list of valid geographical codes (Norwegian:
    forretningsområdekoder). Geographical codes are used to identify the
    organizational units. This file is *not* imported every night. It is used
    at deployment time to register the constants representing the geographical
    codes. 

  * ``feide_orgenh.txt``. A list of organizational units known to
    SAP. Currently this file is *not* used for anything, since FS is the
    authorative source for organizational structure (and SAP OU
    identifications are registered in FS as well).
  
    However, this file *could* be used to check that *all* OUs known to SAP
    are known to FS, and warn about the differences (there is already a job
    that does just that).

  * ``feide_persondata.txt`` lists all employees known to SAP. The file
    contains names, idenfitications, birth dates, addresses and so on. This
    file is imported nightly and the information in Cerebrum is updated with
    its content.

  * ``feide_persti.txt`` lists all employments known to SAP. Only the valid
    employments (more on this later) lead to granting people employee (ANSATT)
    affiliations.

  * ``feide_stilltype.txt`` lists employment codes (SAP.STELL) and the mapping
    between SAP's employment codes and the 4-digit Norwegian state-employee
    employment codes. There has been a bit of confusion regarding the
    Norwegian name for SAP codes, since "stillingskode" and "stillingstype"
    have both been used. The problem is that there is a different *personal*
    employment code (SAP.PLANS), listed in the file
    ``feide_stillkode.txt``. Although this file has been largely ignored, its
    codes appear in ``feide_persti.txt``.

    The employment codes are not imported on a daily basis. Rather, the file
    is used during the setup stage to register the proper constants for SAP,
    much like ``feide_forromr.txt``. 

  * ``feide_utvalg.txt`` lists the registed committees (Norwegian: utvalg) in
    use at each institution. This file, much like ``feide_forromr.txt`` is
    used only once during the setup stage to populate Cerebrum with the proper
    constants. However, its companion file, ``feide_perutvalg.txt``, that
    lists people's participation in committees, is imported daily. 


File format
------------
All files share the same format. It is a variation of a csv-theme. Each
"record" is represented by one line. The fields in a record are separated by
";" (semicolon). If a semicolon occurs within a field, it's escaped by "\"
(backslash). How backslashes are escaped has never been specified. The parsing
happens by splitting and post-processing each line with ``re``
(``mod_sap_utils.py``), but we may want to consider using the ``csv`` python
module. The files are in ISO-8859-1, but this encoding has never actually been
promised. 

Each file has a fixed number of fields per line. The number of fields varies
from file to file. 

The meaning of the fields is based on the original specification handed to
Cerebrum by HiA: 

  * ``feide_orgenh.txt``: ::

      10000054;Stab Ledelsen;0000000014;Studiesekretariat;0011;Stab led;10000053

    ... has 7 fields which are (in order): 

      #. SAP OU id. A magic, non-unique number which identifies OUs uniquely
         together with the geographical code.
      #. OU name. 
      #. Ignored, since unused (Norwegian description: nummer på kostnadssted). 
      #. Ignored, since unused (Norwegian description: navn på kostnadssted).
      #. Geographical code. This number must occur in ``feide_orgenh.txt``
      #. OU short name.
      #. Parent OU id. There is an implicit assumption here that the child and
         the parent share the same geographical code. Since FS is the
         authoritative source with regard to OU structure, the parent id
         irrelevant to Cerebrum.

    The file is not actually used for anything at present, since:

      #. FS is authoritative with regard to OU-hierarchy.
      #. The SAP OU id is registered in ``fs.sted.stedkode_konv`` and that
         column used to populate Cerebrum with the necessary information to
         identify OUs.
    
    Potentially we could run some kind of consistency checker between SAP and
    FS.

  * ``feide_persondata.txt`` has 37 fields, where the ones important to
    Cerebrum are (counted from 0):

      * ** 0**: SAP employee number (a magic number)
      * ** 3**: Initials 
      * ** 4**: Norwegian national ID number (fnr)
      * ** 5**: Birthdate
      * ** 6**: First name
      * ** 7**: Middle name
      * ** 8**: Surname
      * **12**: Private phone number
      * **13**: Contact phone
      * **14**: Contact cellular phone
      * **18**: C/O field (address) 
      * **19**: Street field (address) 
      * **20**: House number field (address) 
      * **21**: Extra address field
      * **22**: City field (address) 
      * **23**: Zip code field (address) 
      * **24**: Country field (address) 
      * **25**: Geographical code (forretningsområdekode)
      * **25**: Private cellular phone
      * **28**: Work title
      * **33**: Death status
      * **36**: Publishable tag (whether the person can be published in
                electronic catalogs (e.g. LDAP))

    Middle name is merged with first name for the time being. Any of the
    fields may be empty (although the import jobs will protest if critical
    fields like IDs are missing). 

    "Death status" is used for two purposes -- marking deceased people (by the
    keyword "Død"), and marking retired people. How retirees are marked is yet
    to be determined. 

    Since SAP offers no interface to track ID changes (employee# and fnr),
    there is no direct way to figure out when a person's fnr changes. Even
    worse, despite the promise that employee# would have a 1-to-1
    correspondance with people, there have been incidents of people having
    multiple employee#. In order to (partially) remedy the situation, the
    import script checks that the (employee#, fnr) *pair* in the file matches
    the corresponding *pair* in Cerebrum.
    
  * ``feide_persti.txt``: ::

      12345678;10000102;30000892;20001008;0032;20031101;99991231;H;70.00

    ... has 9 fields, which are in order:

      * SAP employee number
      * SAP OU number
      * Personal employment code (SAP.PLANS)
      * Employment code (SAP.STELL). This is the one actually being used.
      * Geographical code (forretningsområdekode). 
      * Start date
      * End date
      * Employment kind (H = Hovedstilling, B = Bistilling)
      * Percentage of the employment (0-100). 
      
    There are a few caveats here as well. start/end dates, although initially
    just that, turned out to be used for more than simply employment interval
    designation. In several cases at HiA an employee resigning from a position
    is registered with a "new" employment, where the start date is actually
    the end date for the current employment. This "inversion" of the field
    meaning is presently (2007-04-13) not handled in any adequate fashion.

    Since new employment codes appear every now and then, it is important to
    check the employment code (SAP.STELL) validity before importing the
    records into Cerebrum.
    
    This file is used primary to figure out who the active employees are and
    to assign them ANSATT and TILKNYTTET affiliations.

  * Committees files, ``feide_perutvalg.txt``: ::

      12345678;10000102;0032;K810;20031101;99991231;manager

    ... is an example. The 7 fields are (in order):

      * SAP employee number
      * SAP OU number
      * Geographical code (forretningsområdekode)
      * Committee (from ``feide_utvalg.txt``)
      * Start date
      * End date
      * The role in the committee (free text)

    Today (2007-04-13) this is the least tested part of Cerebrum, since no
    institution has yet used these data for anything meaningful. 


Special values
---------------
Certain (esp. code) values have special meaning in the SAP files and records
with these values should be treated differently from all other records. 

9999 med venner. 
Valid employment entries. In fact, valid anything entries.


Cerebrum DB schema
===================
sketch the database model
constants used. 


Cerebrum API
=============
various mixins
explain what different files contain

