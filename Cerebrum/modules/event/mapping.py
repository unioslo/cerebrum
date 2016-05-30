#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
u""" Module for setting up mappings between events and actions. """

from collections import defaultdict


class CallbackMap(object):

    u""" An event decorator that maps events to callbacks.

    Example use:

    >>> class Foo(object):
    >>>     emap = CallbackMap()
    >>>     @emap('foo', 'bar')
    >>>     def foo_or_bar(*args):
    >>>         print 'foo_or_bar called with args', repr(args)
    >>>     def handle(self, event_name):
    >>>         for cb in self.emap.get_callbacks(event_name)
    >>>             cb(self, 1, 2, 3)
    >>> Foo().handle('foo')

    NOTE: If the decorated function is a method or class method, you will have
          to add the object or type as the first argument when you call the
          callback.
    """

    def __init__(self):
        u"""Initialize callback lookup table. """
        self._callback_lut = defaultdict(list)

    def add_callback(self, event_key, cb):
        u""" Add a callback to the lookup table.

        :param str event_key:
            The event name to register the callback under.
        :param callable cb:
            A callable function to map.

        :raises TypeError:
            If the event_key or callable are the wrong type.
        """
        if not callable(cb):
            raise TypeError(
                u'Invalid callback {!r}, must be callable'.format(cb))
        self._callback_lut[event_key].append(cb)

    def get_callbacks(self, event_key):
        u""" Get callbacks added for a given event.

        :param str event_key:
            The event name to fetch callbacks for.

        :return list:
            A list of callables.
        """
        if event_key not in self._callback_lut:
            return []
        return self._callback_lut[event_key]

    def __call__(self, *events):
        u""" Registers decorated function with the given events.

        :param *list events:
            A list of event names to add the decorated function to.

        :return callable:
            Returns a function decorator.
        """
        def register(func):
            for event_key in events:
                self.add_callback(event_key, func)
            return func
        return register

    @property
    def events(self):
        return self._callback_lut.keys()
