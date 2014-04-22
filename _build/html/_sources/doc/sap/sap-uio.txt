====================
SAP details for UiO
====================

.. contents:: Table of contents
.. section-numbering::


Introduction
=============

This document describes data processing for the SAP-originated data at the
University of Oslo. The main goal is to provide an overall description of the
data exchanged, the jobs involved, the representation of data in-memory, and
so forth.

At UiO, SAP provides the employee data, which is used to populate Cerebrum
with information ranging from names to affiliations, specific e-mail domains,
and so on. Originally, LT (Lønns- og Trekksystemet) was the source of these
data, so it was (and still is) important to introduce support for SAP
gradually, so as to be able to import data from either source.

Note that there are other Cerebrum installations that use SAP. However, the
details between UiO and these installations vary to a great extent.


Overall dataflow description
=============================

Today, 2007-04-11, despite the fact that SAP is used for testing purposes
only, all the major code parts are in place to switch between SAP and LT
rather easily. This was also one of the main goals for the
implementation. Whether the data originates from SAP or LT, does not really
matter, although obtaining the data files is a bit different: ::

  +---+ rsync +--------+            
  |sap| ----> |minister| -------------+---+ 
  +---+       +--------+ rsync of SAP |   ^
                                 data |   | rsync of files back to SAP
                                      |   |
                                      |   |
                                      |   |
  +----+     import_from_LT.py        v   |
  | FS | ------------------------> +----------+ /cerebrum/dumps/SAP
  +----+                           |cerebellum| /cerebrum/dumps/LT
  fsprod.uio.no                    +----------+
                                        |
                                        | import_OU.py
                                        | import_HR_person.py
                                        v
                                 +-------------+ 
                                 |cerebrum_prod|
                                 +-------------+

``import_OU.py`` (populates cerebrum with information about OUs) and
``import_HR_person.py`` (populates cerebrum with information about employees)
can work on either LT or SAP files. There is an abstraction layer that hides
the file specifics from these jobs and makes it possible to work with either
data source.

The data is fetches daily (or, rather, nightly). Fetching the files and
importing HR system data into Cerebrum are about the very first nightly jobs
that are run.


The jobs involved
==================

Works with either input source:

 +-------------------------------+--------------------------------------------+
 | ``import_OU.py``              | Importing OU-data/structure.               |
 +-------------------------------+--------------------------------------------+
 | ``import_HR_person.py``       | Importing employee data.                   |
 +-------------------------------+--------------------------------------------+
 | ``update_employee_groups.py`` | Group updates for groups                   |
 |                               | "uio-tils"/"uio-ans".                      |
 +-------------------------------+--------------------------------------------+
 | ``generate_frida_export.py``	 | Export information to the FRIDA system.    |
 +-------------------------------+--------------------------------------------+
 | ``dump_to_UA.py``             | Export information to the access control   |
 |                               | system (keycards).                         |
 +-------------------------------+--------------------------------------------+

Works with LT only:

 +---------------------+------------------------------------------------------+
 | ``fnr_update.py``   | Updating fnr information from LT. This does not exist| 
 |                     | for SAP (it is unclear how SAP plans to maintain the |
 |                     | fnr-changes).                                        |
 +---------------------+------------------------------------------------------+
 | ``quota_update.py`` | Printer quota information.                           |
 +---------------------+------------------------------------------------------+


SAP data files 
===============

The data files exchanged between Cerebrum and SAP are:

  * ``sap2bas_YYYY-MM-DD-num.xml``, where: 

      * YYYY - 4-digit year
      * MM - 1 or 2-digit month
      * DD - 1 or 2-digit day
      * num - random number (at least random to Cerebrum)

  * ``bas2sap_data.xml``

The former contains *all* the information about employees and OUs in one file
(with LT files, OU and person data are split). The latter has the
fnr/name/e-mail/phone information.

Both files are in XML. The DTD for the sap2bas files is useless, since every
element is marked as carrying CDATA.


sap2bas
---------
sap2bas files are "containers" with all information about each entity packed
inside one element. E.g. everything about a person is registed as subelements
of ``<sap_basPerson>``. There are roughly these categories:

  * personal information and IDs (SAP ID number and fnr), all in ``<person>``
    sublement
  * various addresses in ``<Adresse>`` elements. The elements can be
    distinguished by looking at the ``<AdressType>`` subelement. There are no
    guarantees as to repetition/uniqueness of addresses.
  * Various contact information entries, each in ``<PersonKomm>``. We have
    information like phones numbers, e-mails, UNIX usernames, etc.
  * Primary employment (hovedstilling) in a ``<HovedStilling>``
    element. There can be at most one such element.
  * Other employments (bistillinger) in ``<Bistilling>`` elements. 
  * Roles (roller) in ``<Roller>`` elements. 

Additionally, there are special "rules" for processing the content of
some of the elements.


Abstractions
-------------

