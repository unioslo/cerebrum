Cerebrum developer documentation
--------------------------------
Documentation of Cerebrum internals, intended for programmers with
some Python experience.

* `Writing Cerebrum extensions <extensions.html>`_

  Common patterns for Cerebrum extensions, with example code.

* `Coding conventions <codestyle.html>`_

  Common naming for Cerebrum methods/classes/modules, special SQL
  syntax, how to write docstrings, etc.

* `Hacking Cerebrum <hacking.html>`_

  Practical tips and tricks for Cerebrum programmers.

* `Database schema <database-schema.html>`_

  Cerebrum stores its data in a relational database; this document
  describes the structure of this database.

* `The Cerebrum Core <cerebrum-core.html>`_

  Cerebrum configuration: default_config and cereconf.

  Database layer: Database, SqlScanner, db_row, ChangeLog,
    DatabaseAccessor.

  Object-relational layer: Entity and subclasses, mark_update
    metaclass, mixin classes, Constants.

  Configurable mixin class layer: Factory.

  Other stuff in Core: logging, Metainfo, Utils, Cache, extlib,
    Errors, QuarantineHandler.

* `About expire_date <expire_date.html>`_
  Information about how the expire-date should be handled.  (TBD:
  should be incorporated in cerebrum-core.rst?)

..
