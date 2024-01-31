# -*- coding: utf-8 -*-
#
# Copyright 2016-2023 University of Oslo, Norway
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
This module defines all necessary config for the publishing AMQP client.

Example YAML-config, ``event_daemon.yaml``:
::

    event_publisher:
      connection:
        host: "mq.example.org"
        port: 5671
        ssl_enable: true
        virtual_host: "default"
        username: "guest"
        password: "plaintext:guest"

      exchange:
        durable: true
        exchange_type: "topic"
        name: "from_cerebrum"

    event_formatter:
      issuer: "https://api.example.org/"
      urltemplate: "https://api.example.org/v1/{entity_type}/{entity_id}"
      keytemplate: "org.example.scim.{entity_type}.{event}"

    event_daemon_collector:
      run_interval: 180
      failed_limit: 10
      failed_delay: 1200
      unpropagated_delay: 5400
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.config.loader import read, read_config
from Cerebrum.config.configuration import (Namespace,
                                           Configuration,
                                           ConfigDescriptor)
from Cerebrum.config.settings import Integer
from Cerebrum.modules.amqp.config import PublisherConfig

from .scim import ScimFormatterConfig


# AMQP client config

class EventCollectorConfig(Configuration):
    """ Configuration of the event collector. """

    run_interval = ConfigDescriptor(
        Integer,
        minval=1,
        default=180,
        doc='How often (in seconds) we fetch events')

    failed_limit = ConfigDescriptor(
        Integer,
        minval=1,
        default=10,
        doc='How many times we try to re-queue an event')

    failed_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=20*60,
        doc=('How long (seconds) should we wait before processesing the '
             'event again'))

    unpropagated_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=90*60,
        doc=('How old (seconds) should an event not registered as '
             'processesed be before we enqueue it'))


class EventDaemonConfig(Configuration):

    event_publisher = ConfigDescriptor(
        Namespace,
        config=PublisherConfig)

    event_formatter = ConfigDescriptor(
        Namespace,
        config=ScimFormatterConfig)

    event_daemon_collector = ConfigDescriptor(
        Namespace,
        config=EventCollectorConfig)


def _load_partial_config(cls, root_name, filepath):
    """ Try to load a given config into a config class `cls`. """
    config = cls()
    if filepath:
        config.load_dict(read_config(filepath))
    else:
        read(config, root_name)
    config.validate()
    return config


def load_publisher_config(name='event_publisher', filepath=None):
    """ Load event publisher config.

    Loads config from `filepath` if given, or looks for a config in the default
    location named `name`.
    """
    return _load_partial_config(PublisherConfig, name, filepath)


def load_formatter_config(filepath=None):
    """ Load SCIM formatter config.

    Loads config from `filepath` if given, or looks for a config in the default
    location named 'event_formatter'.
    """
    return _load_partial_config(ScimFormatterConfig,
                                'event_formatter',
                                filepath)


def load_daemon_config(name='event_daemon', filepath=None):
    """ Load event daemon config.

    Loads config from `filepath` if given, or looks for a config in the default
    location named 'event_daemon'.
    """
    return _load_partial_config(EventDaemonConfig, name, filepath)
