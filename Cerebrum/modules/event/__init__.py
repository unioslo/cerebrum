# -*- coding: utf-8 -*-

# Copyright 2013-2023 University of Oslo, Norway
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
Internal Cerebrum event handlers.

This module contains generic utils for dealing with the :mod:`multiprocessing`
module, as well as specific utils for processing events from
:mod:`Cerebrum.modules.EventLog` and similar database notifications.

:mod:`.processes`
    General purpose multiprocessing mixins for dealing with:

    - stoppable daemon processes
    - logging (reset logging and log everything to a
      :class:`Cerebrum.logutils.mp.handlers.ChannelHandler`
    - database connections
    - producing and consuming items from a shared queue

:mod:`.evhandlers`
    Specific process implementations for dealing with database notifications,
    and either *producing* events to a queue, or *consuming* events from a
    queue.

    The overall design is:

    1. A process listens for database notifications, creates events, and pushes
       events to a multiprocessing queue.  These classes are based on the
       :class:`.evhandlers.DBListener` / :class:.evhandlers.EventLogListener`
       classes.

    2. One or more processes pops and processes events from the queue.  These
       are based on the :class:`.evhandlers.DBConsumer` /
       :class:`.evhandlers.EventLogConsumer`.

    3. Optionally, a *collector* class to deal with *failed* events.  E.g.
       :class:`.evhandlers.EventLogCollector`.

:mod:`.mapping`
    Callback mappers for deciding which callback to use with various events.

    These mappers are typically used in actual target system consumers, like
    ``Cerebrum.modules.cim``, ``Cerebrum.modules.exchange``.

:mod:`.utils`
    Various utils for building and starting a *service* that runs processes
    from :mod:`.processes` and :mod:`.evhandlers`.

:mod:`.bofhd_event_cmds`
    Bofhd commands for dealing with :mod:`Cerebrum.modules.EventLog` events.
"""
