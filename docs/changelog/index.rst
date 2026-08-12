==========
ChangeLog
==========

``Cerebrum.ChangeLog`` is an abstract API for handling *changes* in the Cerebrum
database.

.. contents::


Overview
==========
The *changelog* system adds support for *acting* on core database changes.
Whenever a row is added, updated, or removed in the database, the
``ChangeLog`` `log_change`_ method is called.

This call can be delegated to zero or more *implementations* of the abstract
ChangeLog using mixins.


CLDatabase
----------
Support for ChangeLog is patched into the database class using the
``CLDatabase``.  This class merges the the DB-API and the changelog API_ into
*one* class.

Changes are typically logged using ``ChangeLog.`` `log_change`_, and flushed by
the database commit.

On commit, the CLDatabase runs the following steps:

1. pre-commit: ``ChangeLog.`` `write_log`_
2. ``Database.commit``
3. post-commit:

  a. on success: ``ChangeLog.`` `publish_log`_
  b. on failure: ``ChangeLog.`` `unpublish_log`_

On database rollback, the flow is a lot simpler:

1. pre-rollback: ``ChangeLog.`` `clear_log`_
2. ``Database.rollback``


Configuration
--------------
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
-------------
Change types are a separate class of constants, and are included in calls to
`log_change`_.

Available change types are implemented as a
``Cerebrum.Constants._ChangeTypeCode``, and should be present in
``cereconf.CLASS_CLCONSTANTS``.


API
====
ChangeLog is an abstract API for registering and handling events and changes in
Cerebrum.  The API consists of the following methods:


``cl_init``
-----------
Changelog setup method.  `log_change`_ calls will typically fail if setup hasn't
been done to the changelog object.


``log_change``
---------------
Queue a change or event.

Note that no changes or events should be effectuated until `write_log`_ is
called.


``write_log``
--------------
Write, send, commit, or otherwise finalize queued changes.  Changelog
implementations should use this method to prepare and/or deliver changes to the
target system.

Note that ``write_log`` is called *before* changes are commited to the Cerebrum
database.

* Implementations using the same database transaction as Cerebrum (and the
  actual changes that it represents), should ensure that the changes are written
  to the database  (see `Cerebrum.modules.ChangeLog`_).

* Implementations using a different transaction, should ensure that all events
  are written to its current transaction.

* Implementations that *doesn't* use transactions, or otherwise have no support
  for aborts/rollbacks, should *not* use this function, or write changes as
  *tasks* or similar units to the Cerebrum database, for later processing.


``clear_log``
--------------
Clears all events/changes from the current write queue.

Implementations should clear all changes that has been added by `log_change`_.
This is a ChangeLog abort/rollback.


``publish_log``
----------------
Execute events/changes.

This method should process the ChangeLog queue and ensure all events/changes are
processed or delivered.

* Implementations using the same database transaction as Cerebrum should not
  implement this method, but rely on the final database commit (see
  `Cerebrum.modules.ChangeLog`_).

* Implementations using a different transaction, should ensure that its current
  transaction is commited.

* Implementations that *doesn't* use transactions, or otherwise have no support
  for aborts/rollbacks, should use this to deliver/process all events/changes in
  the queue.

Note that the internal *changelog queue* must be emptied by this method.


``unpublish_log``
------------------
Cancel the current publishing queue.

Implementations should use this method to abort delivery/storage of changes.

* Implementations using the same database transaction as Cerebrum should not
  implement this method, but rely on the outcome of the failing database ``commit``.

* Implementations using a different transaction, should ensure that its current
  transaction is rolled back, if possible.

* Implementations that *doesn't* use transactions, needs to figure out how to
  best deal with this situation.

Note that the internal *changelog queue* must be emptied by this method.


Implementations
=================

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
individual target systems*, so each ``log_change`` call can result in multiple
events.

A separate target system mapping tables decides if `log_change`_ calls should
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
   they are commited.


Implementing a changelog
=========================
Implementing changelogs aren't always straight forward.

Atomicity and consistency
    When communicating with an external system, it is *really* hard to guarantee
    that changes are delivered on commit.  The best approach is usually to have
    an internal database queue that is commited along with the actual changes,
    and then flush this queue periodically.

Slow commits
    By delaying processing and database writes to ``publish_log``, the database
    ``commit`` can become very expensive and time consuming.  It's usually best
    to perform as much processing (and ideally database writes) in the
    ``log_change`` call, if possible.

    Doing writes here will break the ``clear_log`` functinality however.  We
    should look into changing the API to better support writes with
    ``log_change``.

``ChangeLog.__init__``
    Changelog implementatinos should not use ``__init__``, as this could easily
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
    API_:
    ::

        db_cls = Factory.get('DBDriver')

        class MySpecialEventLog(EventLog, db_cls):
            def commit(self):
                self.write_log()
                super(MySpecialLogger, self).commit()

        event_log = MySpecialEventLog()
        event_log.log_change(*args)
        event_log.commit()
