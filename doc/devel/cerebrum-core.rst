===================
 The Cerebrum Core
===================

.. contents:: Contents
.. section-numbering::


Configuration
=============

TODO: we need to read through table descriptions in design/core_tables.sql
TODO: This section needs a re-write. The file should look something like this:

* The ``Cerebrum.default_config`` module - general description, shorter
* The ``cereconf`` module - general description, shorter
* Common configuration parameters:
  
   - examples of use of configuration parameters in configuration of own
     Cerebrum instalation
   - description/illustration of usage of default values/overriding of
     parameters to gain flexibility/change the behavior of Cerebrum
   - detailed description of the most important parameters and their
     function
   - a reference to default_config.py for more information on other 
     parameters.

The ``Cerebrum.default_config`` module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cerebrum has fairly large number of configurable parameters that may
be adjusted by the system administrator.  These parameters include
things like the database name and driver.  *All* such parameters
should have an entry with its default value in the module called
``Cerebrum.default_config``, and every such entry should be
accompanied by a comment on the intended purpose for that particular
configurable.

For parameters where no generally useful default can be found, the
default value should be invalid for that parameter, and a statement to
the effect of:

  If you want to use this functionality, you must override the default
  value in cereconf.py

should be included in the parameters comment.


The ``cereconf`` module
~~~~~~~~~~~~~~~~~~~~~~~
As the ``default_config`` module lives in the ``Cerebrum`` Python
package, an upgrade of Cerebrum will replace the module.  Hence, if
you want to change any of the default values, don't change them in
``default_config``; rather, you should set "your" values in the
``cereconf`` module.

The ``cereconf`` module will typically reside in
``$CEREBRUM_ROOT/etc/cerebrum/cereconf.py``.

The file is a Python script, thus it must contain valid Python syntax.
Most of the settings are of the type ``key = value``.  On a fresh
install, the file only contains the following line (excepting lines
starting with #, which are Python comments):

  ``from Cerebrum.default_config import *``

This imports all the default settings for Cerebrum.  Normally this
line should never be changed or removed, and all your own settings
should appear below it.


cereconf.py in a testing environment
------------------------------------
If you have one production, and one testing environment, and want to
assert that your test environment allways includes the settings from
the production environment, you can use a ``cereconf.py`` that looks
something like this::

   # -*- coding: iso-8859-1 -*-
   import os
   # Import settings from production environment
   execfile(os.path.join(os.path.dirname(__file_),
                         "cereconf-production.py"))

   # Then override as needed
   _hostname = os.uname()[1]
   if _hostname in ('testmachine.foo.com',):
       CEREBRUM_DATABASE_NAME = "cerebrum_testing"


Common configuration parameters
-------------------------------
This section contains a brief explanation of some of the common
parameters.  A description of all the available parameters is beyond
the scope of this document; they are documented in
``Cerebrum/default_config.py``.

   *Note*: As mentioned in the Factory documentation, some classes are
   created dynamically from a list of classes.  The parameters
   specifying these class lists are named ``CLASS_*``, e.g.::

     CLASS_DBDRIVER = ('Cerebrum.Database/PostgreSQL',)

   Observe the important comma just before the closing parenthesis --
   without that comma, Python would interpret that value as a string,
   and not a list, and things would stop working.

TBD: Hvor mye tekst vil vi egentlig ha her?

``CEREBRUM_DATABASE_NAME = 'cerebrum_db'``
  Defines the name of the Cerebrum database to use.

``CEREBRUM_DATABASE_CONNECT_DATA['user'] = 'cerebrum'``

  Defines the (database) username used for connecting to the database.
  The corresponding password is stored in
  ``$CEREBRUM_ROOT/etc/passwords/passwd-<user>@<database_name>``
  (which must be readable by the (Operating System) user used for
  running Cerebrum's Python scripts.

``CLASS_DBDRIVER = ('Cerebrum.Database/PostgreSQL',)``
  Defines that Cerebrum (by default) should use PostgreSQL drivers
  when connecting to databases.

``CLASS_CONSTANTS = ('Cerebrum.modules.PosixUser/Constants', 'Cerebrum.modules.CLConstants/CLConstants')``
  Defines which Cerebrum constants ("code values") should be available.

``CLASS_CHANGELOG = ('Cerebrum.modules.ChangeLog/ChangeLog',)``
  Indicate which changelog class we want to use.  This one enables the
  changelog, while the default one is an empty implementation.

``PERSON_NAME_SS_ORDER = ("system_lt", "system_fs", "system_ureg")``
  The ordering in which we trust person names from source systems.
  Used when updating the names of the person in the magic source
  system named 'cached'.



The database layer
==================


``Cerebrum.Database``
~~~~~~~~~~~~~~~~~~~~~

- Provides a compatibility wrapper around various python DB-API 2.0
  drivers.
- Currently has support for connecting to Oracle and PostgreSQL
  databases.
- Specific drivers supported:
  - ``pyPgSQL.PgSQL`` (fully supported)
  - ``psycopg`` (some support; probably still somewhat buggy)
  - ``DCOracle2`` (fully supported for connecting to non-Cerebrum
  Oracle databases)


Extensions to SQL syntax
------------------------
- The classes in the ``Database`` module implements some special SQL
  syntax extensions.  In SQL statements, these syntax extensions look
  like this::

    [:function key1=val1 key2=val2]

  The Python code implementing these syntax extensions reside in
  methods called ``_sql_port_*``, so that the *:function* extension
  resides in method ``_sql_port_function()``.

  The following extensions are currently supported:

  - \[:table schema=cerebrum name=entity_info\]

    Expands to ``entity_info`` on PostgreSQL, but
    ``cerebrum.entity_name`` on Oracle.

  - \[:now\]

    Expands to the current datetime.

  - \[:sequence schema=cerebrum name=entity_id_seq op=next\]

    SQL sequence access; valid operations for ``op`` are ``current``
    and ``next``.

  - \[:from_dual\]

    Oracle won't accept SELECT queries with no FROM clause, and
    PostgreSQL doesn't have anything curresponding to Oracle's special
    DUAL table.

Python interface
----------------
The module defines two main classes: 
``Database`` and ``Cursor``.

query(self, query, params=(), fetchall=True)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(TODO: extract python method doc)

query_1(self, query, params=())
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(TODO: extract python method doc)

execute(self, operation, parameters=())
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(TODO: extract python method doc)

connect(\*args, \*\*kws)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(TODO: extract python method doc)


db_row
------
Data returned from execute() are db_row objects, which makes it
possible to reference them by column name.


Metainfo
========
Stores meta information about the database, such as the version number
of the installed database schema, and the version of each --extra-file
that was used when running ``makedb.py``


Utils
=====
TBD: ettersom denne inneholder Factory, auto_super og mark_update bør
den kanskje dokumenteres der?

Provides a number of general utility functions/classes.  We should
probably consider splitting it into smaller pieces.


logging
=======
<her skal igorr's dok inn>

..
