.. namespace:: devel-database-schema

============================
The cerebrum database schema
============================

.. contents:: Contents
.. section-numbering::

.. sysinclude::
  :vardef: ext_sqldoc $ENV[CEREDOC]/scripts/ext_sqldoc.py --file $ENV[CERESRC]/design/core_tables.sql 

Introduction
============

Cerebrum stores (most of) its information in a database.  The database
consist of a set of core tables that are present in all cerebrum
installations.  Some modules add additional tables to support data
they need.  For example: if one wants support for unix users, one
would need the posix module that has extra tables for posix specific
attributes.

A diagram of the core tables can be seen in <TODO>.  It is also
available in ``design/cerebrum-core.dia``, which may be loaded with
the unix-program dia (http://www.lysator.liu.se/~alla/dia/) (due to a
bug in dia, the fonts may have wrong size on some systems).

The diagram contains several small boxes where the title represents
the table name, and the rows below indicate the columns and their
type.  For simplicity the tables are grouped in various areas with
different colours, where each colour represent different types of
information.  For instance the pink area contains tables that relate
to organisational units.


entity_info
-----------

Entities is a central concept in cerebrum.  Persons, user, groups
etc. are examples of various entities.  Each entity has an entry in
``entity_info``, which contains a numerical id, ``entity_id``, as well as the
type of entity, ``entity_type``.  In addition the entity has entries in
various tables depending on its type.  These tables will have the same
value for ``entity_type`` and ``entity_id``.  For example:

  An organicational unit would have an entry in ``entity_info ei``, and
  ``ou_info oi`` where ``ei.entity_type=oi.entity_type`` and
  ``ei.entity_id=ou.ou_id``.  In addition one could store address
  information for the ou in ``entity_address ea`` with
  ``ei.entity_id=ea.entity_id`` and ``ei.entity_type=ea.entity_type``.

These foreign-keys are represented by the arrows in the diagram.  The
core API in cerebrum limit what types of data that may be associated
with each entity type.  Thus, while the database schema allows a disk
to have an ``entity_address``, the core API don't allow it.


code tables
-----------

Cerebrum has extensive use of code tables which are used to limit the
legal values for various types of data.  All code tables end with the
string ``_code``.  

For instance, the gender for a person is stored in
``person_info.gender`` which is a foreign key to ``gender_code``.  The
legal gender codes are maintained with the various Constants classes.
Code tables avoids problems with the same code value being written in
different ways, for instance 'boy' or 'male' for gender (TODO: bedre
eksempel, boy er ikke et gender), while making it easy to introduce a
new gender code 'unknown'.

Most code tables contains three columns:

- a numerical ``code`` that must always be constant, and which is used as
  a foreign key
- a string ``code_str`` which makes the code more easy to read for humans
  than a plain number
- a ``description``


Database independency
---------------------

In Cerebrum, we have aimed at only using standard SQL, so that it may
be used with any database backend that support a certain set of
features.  These features includes, but are not limited to:

- inner selects
- transaction support
- foreign key support

Currently only PostgreSQL and Oracle >= 9 is supported by the database
module ``Database.py``.  Since we try to be fairly database
independent, we do not use triggers or similar mecanisms.


Constraints
-----------

In order to assert that the database always is consistent, cerebrum
relies heavily on foreign key, and unique constraints.  This prevents
things like 

- a ``person_info`` entry being registered with the same ``entity_id``
  and ``entity_type`` as an ``ou_info`` entry.

- a ``group_info`` entry being deleted while it still has
  ``group_members``

- two accounts being registered with the same name

... and so on

Some constraints are too complex to express with these mecanisms (see
above why we don't use triggers).  For instance a unix username may
only contain certain characters.  Such constraints are enforced by the
API.  If users are allowed to use SQL to directly modify the cerebrum
database, they should be careful not to violate any API constraints.


table descriptions
==================

TODO: Skal vi ta med beskrivelse av hver tabell her?  Tror det hadde
vært fint, men vi vil _ikke_ duplisere informsajonen vi allerede har i
core_tables.sql, så den må enten flyttes, eller så må vi finne på noe
lurt som kan ekstrahere den automagisk.

.. TODO: sql-komentarene er ikke på ReST format, bruker literal intil
   dette er fikset

entity_info
-----------
.. sysinclude:: %(ext_sqldoc)s --table entity_info
  :literal:

entity_spread
-------------
.. sysinclude:: %(ext_sqldoc)s --table entity_spread
  :literal:


entity_name
-----------
.. sysinclude:: %(ext_sqldoc)s --table entity_name
  :literal:


entity_address
--------------
.. sysinclude:: %(ext_sqldoc)s --table entity_address
  :literal:


entity_contact_info
-------------------
.. sysinclude:: %(ext_sqldoc)s --table entity_contact_info
  :literal:


host_info
---------
.. sysinclude:: %(ext_sqldoc)s --table host_info
  :literal:


disk_info
---------
.. sysinclude:: %(ext_sqldoc)s --table disk_info
  :literal:


account_info
------------
.. sysinclude:: %(ext_sqldoc)s --table account_info
  :literal:


account_home
------------
.. sysinclude:: %(ext_sqldoc)s --table account_home
  :literal:


cerebrum_metainfo
-----------------
.. sysinclude:: %(ext_sqldoc)s --table cerebrum_metainfo
  :literal:


entity_quarantine
-----------------
.. sysinclude:: %(ext_sqldoc)s --table entity_quarantine
  :literal:


ou_info
-------
.. sysinclude:: %(ext_sqldoc)s --table ou_info
  :literal:


ou_structure
------------
.. sysinclude:: %(ext_sqldoc)s --table ou_structure
  :literal:


ou_name_language
----------------
.. sysinclude:: %(ext_sqldoc)s --table ou_name_language
  :literal:


person_info
-----------
.. sysinclude:: %(ext_sqldoc)s --table person_info
  :literal:


person_external_id
------------------
.. sysinclude:: %(ext_sqldoc)s --table person_external_id
  :literal:


person_name
-----------
.. sysinclude:: %(ext_sqldoc)s --table person_name
  :literal:


person_affiliation
------------------
.. sysinclude:: %(ext_sqldoc)s --table person_affiliation
  :literal:


person_affiliation_source
-------------------------
.. sysinclude:: %(ext_sqldoc)s --table person_affiliation_source
  :literal:


account_type
------------
.. sysinclude:: %(ext_sqldoc)s --table account_type
  :literal:


account_authentication
----------------------
.. sysinclude:: %(ext_sqldoc)s --table account_authentication
  :literal:


group_info
----------
.. sysinclude:: %(ext_sqldoc)s --table group_info
  :literal:


group_member
------------
.. sysinclude:: %(ext_sqldoc)s --table group_member
  :literal:


..
