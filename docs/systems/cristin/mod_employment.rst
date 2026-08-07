============================
Employment data in Cerebrum
============================

Overview
=========
In order to provide data to Cristin about employees, Cerebrum includes an
optional employment data structure.

This data structure consist of:

``mod_employment.sql``
    Database tables for employment data.


``Cerebrum.modules.no.PersonEmployment``
    Person mixin and database access methods for the employment tables.

Legacy DFØ/SAP import
    The legacy DFØ import for UiA (also used for other institutions) adds
    and updates employment data.


Background
===========
This module was implemented to support the Cristin XML export.

Cristin needs some basic info on employees, the most important being
hovedstilling/bistilling (main- and additional employment roles), as well as
*employment codes* (stillingskode).

A one-way conversion from employment codes to affiliation is already implemented
using ``mod_sap.sql`` and constants, but this doesn't allow us to retain data
about each employment for later use.

``mod_employment.sql`` was a simple solution to store employment data for use
with Cristin (and potentially for other use-cases).


Deploy
=======
To enable ``mod_employment``, Cerebrum will need three things:


1. Schema
2. Config/mixins
3. Data


Schema
------
Add the employment module/table(s) with:
::

    makedb.py design/mod_employment.sql


Config
------
Add mixins to ``cereconf``:


``cereconf.CLASS_PERSON``
    The person class needs
    ``Cerebrum.modules.no.PersonEmployment/PersonEmploymentMixin`` for
    employment support.

``cereconf.CLASS_OU``
    Typically needs location code support. Ensure ``CLASS_OU`` is/contains
    ``Cerebrum.modules.no.Stedkode/Stedkode``.


Import
------
Add ``--with-employment`` to ``process_SAP_affiliations.py`` to enable import of
employment data.
