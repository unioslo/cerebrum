# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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
from __future__ import unicode_literals

"""
This module contains a class used for mapping an incoming message in the form
of an Event object into a callable.
"""

import re

from Cerebrum.utils.module import resolve


class Trigger(object):
    def __init__(self, config):
        # TODO: Should this actually be a new `Regex` Setting?
        self.routing_key = re.compile(config.routing_key)
        self.exchange = config.exchange

    def match(self, exchange, routing_key):
        """Check if self matches the exchange and routing_key of a message"""
        return (self.routing_key.match(routing_key) and
                (self.exchange == '' or self.exchange == exchange))


class Task(object):
    def __init__(self, config):
        self.name = config.name
        call = resolve(config.call)
        assert callable(call)
        self.call = call
        self.triggers = [Trigger(t) for t in config.triggers]


class MessageToTaskMapper(object):
    """Map incoming amqp messages into callables"""

    def __init__(self, config):
        self.config = config
        self.tasks = [Task(t) for t in config.tasks]

    def message_to_callable(self, event):
        """Map an incoming message to a sequence of callables to call

        :type event: Cerebrum.modules.amqp.handlers.Event
        """
        exchange = event.method.exchange
        routing_key = event.method.routing_key
        for task in self.tasks:
            if any(t.match(exchange, routing_key) for t in task.triggers):
                yield task.call
