==========
ChangeLog
==========

``Cerebrum.ChangeLog`` is an abstract API for handling *changes* in the Cerebrum
database.

.. contents:: :local:


Overview
==========
The *changelog* system adds support for *acting* on core database changes.
Whenever a row is added, updated, or removed in the database, the
``ChangeLog.log_change`` method is called.

This call can be delegated to zero or more *implementations* of the abstract
ChangeLog using mixins.


CLDatabase
===========
Support for ChangeLog is patched into the database class using the
``CLDatabase``.  This class merges the DB-API and the Changelog API into
*one* class.

Changes are typically queued using ``ChangeLog.log_change``, and flushed by
a database commit.

On commit, the CLDatabase runs the following steps:

1. pre-commit: ``ChangeLog.write_log``
2. ``Database.commit``
3. post-commit:

  a. on success: ``ChangeLog.publish_log``
  b. on failure: ``ChangeLog.unpublish_log``

On database rollback, the flow is a lot simpler:

1. pre-rollback: ``ChangeLog.clear_log``
2. ``Database.rollback``


Configuration
==============
ChangeLog support is configured using :doc:`/config/cereconf`:

::

    # Use the CLDatabase as our database implementation.
    #
    # Note: This is the only implementation that will actually work with
    # Cerebrum, as most internal database use expects this class to implement
    # the ``cl_init`` and ``log_change`` methods.
    cereconf.CLASS_DATABASE = ("Cerebrum.CLDatabase/CLDatabase", )

    # Select changelog implementations
    #
    # See section on implementations for more suggestions.
    cereconf.CLASS_CHANGELOG = ("Cerebrum.ChangeLog/ChangeLog", )

    # Select database driver
    #
    # Note: Cerebrum has moved away from being database agnostic.  Some
    # functionality may require this to be PsycoPG2.
    cereconf.CLASS_DBDRIVER = ("Cerebrum.database.postgres/PsycoPG2", )


Change types
=============
Change types are a separate class of constants, and are included in calls to
``ChangeLog.log_change``.

Available change types are implemented as a
``Cerebrum.Constants._ChangeTypeCode``, and should be present in
``cereconf.CLASS_CLCONSTANTS``.


Implementations
================

Cerebrum.modules.ChangeLog
---------------------------
The ``Cerebrum.modules.ChangeLog`` module stores changes in its own tables.

Note that this is *legacy functionality*, and that any new use case should use
data from another changelog module.

The purpose of this module is to:

- Leave an audit trail (which change has been performed by who, and when?).
  This is now done better by `Cerebrum.modules.audit.auditlog`_.

- Store events for future processing (together with the
  ``Cerebrum.modules.CLHandler`` module).  This has mainly been replaced by
  ``Cerebrum.modules.event_publisher.eventlog`` and external processing of
  events.


Cerebrum.modules.EventLog
-------------------------
The ``Cerebrum.modules.EventLog`` module is a legacy Publish/Subscribe event
processing module.

In short, certain `change types`_ will result in an *event* being stored in an
*event table* that this module implements.  The event table stores events for
individual *target systems*, so each ``log_change`` call can result in multiple
events.

A separate target system mapping tables decides if changes should
result in queued events.

When a new event row has been queued, our database will immediately notify any
process that is listening for messages to the given *target system*.  Note that
this module uses PostgreSQL specific functionality for sending notifications to
listening processes.

This module was implemented for ``Cerebrum.modules.exchange``, but has also been
used in ``Cerebrum.modules.cim``.


Cerebrum.modules.audit.auditlog
-------------------------------
The ``Cerebrum.modules.audit`` modules implements an audit log system that can
replace `Cerebrum.modules.ChangeLog`_.

This module simply stores all changes presented through the ``log_change``
calls, along with some metadata about the operator and affected entities, to a
separate audit log table.

Unlike ``Cerebrum.modules.ChangeLog``, this module does not have foreign key
constraints to the operator or affected entities.  This means that an audit
record can remain in the database when the entities that the record refers to
are deleted.


Cerebrum.modules.event_publisher.eventlog
-----------------------------------------
The ``Cerebrum.modules.event_publisher`` modules implements a system for
publishing notifications to external systems when changes occur in Cerebrum:

1. on ``log_change``, the change is queued in memory.

2. on ``publish_log``, the internal queue is filtered, simplified, turned into
   basic messages, and flushed to an internal database queue.

3. The database queue is processed and sent to an external message broker using
   the event publisher daemon, which gets notified about new events as soon as
   they are committed.


Implementing a changelog
=========================
Implementing a changelog isn't always straightforward.

Atomicity and consistency
    When communicating with an external system, it is *really* hard to guarantee
    that changes are delivered on commit.  The best approach is usually to have
    an internal database queue that is committed along with the actual changes,
    and then flush this queue periodically.

Slow commits
    By delaying processing and database writes to ``publish_log``, the database
    ``commit`` can become very expensive and time consuming.  It's usually best
    to perform as much processing (and ideally database writes) in the
    ``log_change`` call, if possible.

    Doing writes here will break the ``clear_log`` functionality however.  We
    should look into changing the API to better support writes with
    ``log_change``.

``ChangeLog.__init__``
    Changelog implementations should not use ``__init__``, as this could easily
    lead to conflicts with the ``Database`` init method.

    Any required setup should be done through ``cl_init``.

``log_change``
    Log change has four positional arguments:

    #. ``subject_entity``
    #. ``change_type``
    #. ``destination_entity``
    #. ``change_params``

    Any additional arguments must be keyword arguments.  Unknown keyword
    arguments should be passed through to the parent ``log_change`` method:
    ::

        def log_change(self, subject_entity, change_type, destination_entity,
                       change_params=None, my_special_arg='my_default_value',
                       **other_kw_args):
            super(MySpecialImplementation, self).log_change(
                subject_entity=subject_entity,
                change_type=change_type,
                destination_entity=destination_entity,
                change_params=change_params,
                **other_kw_args,
            )
            # Do stuff with `my_special_arg`

Log changes without CLDatabase
    If you need to log changes using *your* implementation, and no other
    implementations, then this should be done using a custom CLDatabase
    implementation, and not with *hacks* that extends or alters the changelog
    API:
    ::

        db_cls = Factory.get('DBDriver')

        class MySpecialEventLog(EventLog, db_cls):
            def commit(self):
                self.write_log()
                super(MySpecialEventLog, self).commit()

        event_log = MySpecialEventLog()
        event_log.log_change(*args)
        event_log.commit()
