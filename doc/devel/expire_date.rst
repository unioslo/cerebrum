============================
Expiration dates
============================

.. contents:: Contents
.. section-numbering::


Introduction
=============
This document describes how the ``expire_date`` in Cerebrum should be
interpreted.

The ``expire_date`` can be used to put a limit on how long an
``Entity`` in Cerebrum should be valid.  Typically one could create a
guest account for a visiting user, and set its ``expire_date`` 180
days ahead so that one wouldn't have to remember to delete the account
after the guest has left.


Interpretation of ``expire_date``
==================================
The ``expire_date`` takes effect iff it is set for an ``Entity``, and
current-date > ``expire_date``.  We shall then refer to such entities
as expired.  There is no practical difference between an Entity that
has ``expire_date=NULL``, and one that has an ``expire_date`` in the
future.

If an ``Entity`` is expired, any derived entities are also expired.
I.e if an ``Account`` is expired, a corresponding ``PosixUser`` is
also expired.

An expired ``Entity`` will by default *not* be returned by *any*
Cerebrum method that lists entities unless the optional keyword
argument ``filter_expired=False`` is used (it defaults to ``True``).

.. note::
  The above statement probably requires some modifications to the
  current API

All scripts that lookup entities by ``entity_id``, where the
``entity_id`` is not originated from a list method that filters
expired entities, *must* use its corresponding ``is_expired()`` method
to check that the ``Entity`` is in fact still valid.

When the clock ticks past ``expire_date``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The only thing that happens when the clock ticks past ``expire_date``
is that the queries mentioned above will no longer return the
``Entity`` (or ``is_expired()`` will return ``True``).  It is not
automatically removed from the database, and no special jobs are
triggered.

Any actions based on the ``expire_date`` must be setup specifically for
each site.


Cleaning up obsolete data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are both advantages and disadvantages with leaving data related
to an ``Entity`` intact once its ``expire_date`` has passed.  The
obvious advantage with not touching the data is that it is easy to
revert the expiration if it was due to some error.  On the other hand,
obsolete data may clutter up information about group_members etc, and
reviving an expired ``Entity`` may have unexpected side-effects
since the ``Entity`` automatically regains all group_memberships,
spreads etc. that it had prior to deletion.  Premature deletion of
quarantines may again cause reviving of an account who's user had done
something nasty without the quarantine being preserved.

The best solution is probably to gradually remove data related to the
``Entity`` once its ``expire_date`` has passed.

Generalizing ``Entity`` Expiration
===================================
Cerebrum currently uses ``expire_date`` in ``account_info`` and
``group_info``.  We also need this information in ``ou_info``.  It has
been suggested to add ``expire_date`` into the ``entity_info`` table.
This will probably be done in the near future.


Example of expiration policy
==============================
Cerebrums handling of ``expire_date`` is a bit dangerous unless one
provides mechanisms that trigger on a date related to the
``expire_date``.  Typically one would want someone to receive an
e-mail warning a number of days before an ``Entity`` expires.

It is possible to provide such a mechanism by sub-classing the
``Entity`` in question, and making it do something whenever an
``expire_date`` is set.  Alternatively, one could use a change-log
listener to achieve the same effect.  This is the way
``contrib/no/uio/process_changes.py`` handles quarantines, which has a
similar problem.

What one then needs is a mechanism to make something happen on a given
date.  Currently Cerebrum only has one such mechanism:
``bofhd_request``, so we could use that in the same way that
``process_changes.py`` uses it to register actions to trigger at dates
related to the ``expire_date``.

It is recommended that the action stored on the given date should be
"check ``expire_date``", and not "delete user" to avoid problems if
the ``expire_date`` was somehow changed after it was first set.


Users
~~~~~~~
For users one would typically want to send an e-mail notification to
the account-owner X days prior to expiration, and then a reminder Y
days later with a copy to whoever has "bofh rights" over the user.
For such sites, one might consider providing mechanisms in the
user-administration tool that handles the special-case where an
administrator manually sets the ``expire_date`` less than X days
ahead.

On the actual ``expire_date`` one might automatically start a job that
archives and removes the users home-directory, email etc, as it is
probably not a good idea to have data on other systems belonging to
this user, but who now looks like it has no owner.

Some sites may want to completely remove the ``Entity`` from Cerebrum
after some time has passed.

Groups
~~~~~~~
Like for users, one would probably want one or two e-mail reminders.
Some time after expiration, one would remove the group-members, and
some time after that one would probably delete the ``Entity``.
