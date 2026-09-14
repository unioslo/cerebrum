#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2026 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
API for handling *changes* in Cerebrum.

This module implements an abstract event API for logging database changes in
Cerebrum.  Changes are added (logged) whenever a database row related to an
Entity is added, updated, or removed from the database.

Subclasses may implement specific actions for the changes logged using this
API.  To use one or more implementations, they need to be added to the
``cereconf.CLASS_CHANGELOG`` setting.

The resulting *ChangeLog* component gets mixed into the Database API (see the
``CLDatabase`` module) to process changes automatically on commit/rollback, but
can also be used separately.

The typical pattern for logging a change is:

- Call :meth:`.ChangeLog.log_change` whenever a change is performed.  Changes
  are typically added to an in-memory queue.

- Use the :mod:`.CLDatabase` to deal with commit/rollback:

  - Call :meth:`.ChangeLog.write_log` or :meth:`.ChangeLog.clear_log` before a
    commit/rollback

  - Call :meth:`.ChangeLog.publish_log` or :meth:`.ChangeLog.unpublish_log`
    after a commit
"""


class ChangeLog(object):
    """ Abstract API for changes/events. """

    def cl_init(self, **kw):
        """
        Initialize the ChangeLog implementation.

        This sets up the ChangeLog with any state it needs for this (and
        future) transactions.  This typically includes:

        - setting a ``change_program`` to identify what part of Cerebrum the
          change comes from.

        - setting a ``change_by`` for changes made by authenticated users.
        """
        pass

    def log_change(self, *arg, **kw):
        """
        Queue a change or event.

        Note that no changes or events should be persisted or effectuated until
        :meth:`.write_log` is called.
        """
        pass

    def write_log(self):
        """
        Flush queue (pre-commit action).

        Write, prepare, or process the queued changes in a way that can be
        aborted or withdrawn.

        - Implementations using a shared Cerebrum database transaction should
          ensure that the changes are written to the database.

        - Implementations using a different database, should connect, start a
          transaction, and write changes.

        - Implementations that *don't* use transactions, or otherwise have no
          support for aborts/rollbacks, should prepare as much as possible
          without finalizing the changes.

        """
        pass

    def clear_log(self):
        """
        Clear the queue (pre-rollback action).

        This is the inverse of :meth:`.write_log`.  It should clear any
        queued changes, and reset the ChangeLog back to a clean state.
        """
        pass

    def publish_log(self):
        """
        Publish prepared changes (post-commit action).

        This method should process the ChangeLog queue and ensure all
        events/changes are processed or delivered.

        - In implementations using a shared Cerebrum database transaction,
          this is usually a no-op.

        - Implementations using other transactions typically commit here.

        - Implementations without transaction support would typically send
          a prepared payload to the target system.
        """
        pass

    def unpublish_log(self):
        """
        Abort prepared changes (post-commit action).

        This is the inverse of :meth:`.publish_log`.  This is typically called
        whenever a Cerebrum database commit fails, and should abort all planned
        changes for this ChangeLog implementation.

        As with :meth:`.clear_log`, this should reset the ChangeLog state.

        - In implementations using a shared Cerebrum database transaction,
          this is usually a no-op.

        - Implementations using a different transaction would issue a rollback.

        - Implementations without transaction support would typically just
          clean up any prepared payloads.
        """
        pass
