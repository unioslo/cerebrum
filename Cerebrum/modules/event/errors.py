# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
Event-related exceptions.

These errors are used by the *event handlers* in :mod:`.evhandlers` to deal
with events that can't or shouldn't be processed.

TODO: These exceptions should inherit from ``Exception``, and not
``BaseException``.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


class EventExecutionException(BaseException):
    """
    Normally raised when an event fails processing.
    """
    pass


class EventHandlerNotImplemented(BaseException):
    """
    Normally raised when an event type/name is unknown to the handler.

    This is equivalent to a NotImplementedError, and *either* means that we're
    missing an event handler implementation, *or* that we've subscribed to an
    event type that isn't relevant to the given system.

    This *shouldn't* happen - these events should get a noop callback/event
    handler implementation.
    """
    pass


class EntityTypeError(BaseException):
    """
    Typically called when an objects owner type is wrong.

    Similar to :class:`.UnrelatedEvent`, but for cases where the event is
    unrelated because a target entity is of the wrong type.
    """
    pass


class UnrelatedEvent(BaseException):
    """
    Raised for events that should not be processed.

    This is typically used by event handlers to abort processing an event (i.e.
    tell the consumer process that the event should be removed without further
    processing).
    """
    pass
