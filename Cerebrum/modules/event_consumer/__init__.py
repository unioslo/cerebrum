#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
""" Get a client that can be used to consume messages."""

__version__ = '1.0'


def get_consumer(callback_func=None, consumer_name=None, config=None):
    """Instantiate consuming client.

    Instantiated trough the defined config."""
    from Cerebrum.modules.event_consumer.amqp_consumer import (
        ConsumingAMQP091Client as client)
    if not config:
        from Cerebrum.modules.event_consumer.config import load_config

        config = load_config(consumer_name=consumer_name)

    if not callback_func:
        callback_func = client.consumer_callback
    return client(config, callback_func)
