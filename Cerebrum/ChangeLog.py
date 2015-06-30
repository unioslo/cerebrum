#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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
""" The ChangeLog is an Event-API for Cerebrum.

The ChangeLog is designed to link database changes to events. Changes are added
to the log, and can be committed or rolled back. This API is
generally in use with a database backend (see the CLDatabase module), but can
be used separately. When used with a database action, the commit/rollback would
normally be used in concurrence with the database transaction commit/rollback.

The behaviour of ChangeLog implementations should be:

- Call `log_change' whenever a change is performed.

  This should cause a change entry to be created and cached within the
  ChangeLog implementation.

- Call `write_log' whenever changes are persisted.

  This should cause all changes to be flushed to their target system.
  A target system can be a database, a message broker, a service bus or any
  other system.

  This function is typically called BEFORE a database commit.

- Call `clear_log' whenever changes are aborted.

  This should cause all cached changes to be dropped.

  This function is typically called after a database write/commit fails, or
  when performing a database rollback.

- Call `publish_log' to finalize changes

  Used when synchronizing the `write_log' between multiple systems.
  `write_log' and `publish_log' acts as a first and second commit in a
  two-phase commit. Alternately, when working with a transactional system,
  `write_log' will act as a write, and the `publish_log' as a commit
  transaction.

  This function is typically called AFTER a successful `write_log' and
  database commit.

- Call `unpublish_log' to abort any changes

  Used when synchronizing the `write_log' between multiple systems. With a
  transactional system, `unpublish_log' is a rollback after writing with
  `write_log'.

  This function is typically called AFTER an unsuccessful `write_log' or
  database commit.

Note that not all ChangeLog implementations will want to use both
write_log/clear_log AND publish_log/unpublish_log.

"""


class ChangeLog(object):

    """ API for Events. """

    def cl_init(self, **kw):
        """ Initialize the ChangeLog implementation. """
        pass

    def log_change(self, *arg, **kw):
        """ Queue a change for logging.

        Note that the change may not be final when this function is called. Any
        changes that are logged must also be commited to be persistent.

        """
        pass

    def write_log(self):
        """ Flush queued changes. """
        pass

    def clear_log(self):
        """ Drop all queued changes. """
        pass

    def publish_log(self):
        """ Finalize publication of changes. """
        pass

    def unpublish_log(self):
        """ Abort publication of changes. """
        pass
