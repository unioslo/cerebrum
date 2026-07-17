# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
This module defines all necessary config for the event publisher.

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
import textwrap

from Cerebrum.config import loader
from Cerebrum.config.configuration import (
    ConfigDescriptor,
    Configuration,
    Namespace,
)
from Cerebrum.config.settings import Integer
from Cerebrum.modules.amqp.config import PublisherConfig
from Cerebrum.utils.date import to_seconds

from .scim import ScimFormatterConfig


class EventCollectorConfig(Configuration):
    """
    Configuration of the event collector.

    The event collector catches events that are already in the queue for being
    published, but we haven't been notified about for some reason.

    Most of these will be failed events that we want to retry.  It runs
    periodically, and this config decides how often we collect and publish
    these events.
    """

    run_interval = ConfigDescriptor(
        Integer,
        minval=1,
        default=180,
        doc="How often (in seconds) we fetch/look for events to publish",
    )

    failed_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=to_seconds(minutes=20),
        doc=textwrap.dedent(
            """
            How long should we wait (in seconds) before re-trying a failed
            event.
            """
        ).strip(),
    )

    failed_limit = ConfigDescriptor(
        Integer,
        minval=1,
        default=10,
        doc="How many times we re-try to publish an event before giving up.",
    )

    unpropagated_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=to_seconds(hours=1, minutes=30),
        doc=textwrap.dedent(
            """
            How old should an event be (in seconds) before we publish it.  This
            mainly deals with events where we've missed the notification for
            some reason.
            """
        ).strip(),
    )


class EventDaemonConfig(Configuration):
    """
    The full config file structure for our event publisher daemon.
    """

    event_publisher = ConfigDescriptor(
        Namespace,
        config=PublisherConfig,
    )

    event_formatter = ConfigDescriptor(
        Namespace,
        config=ScimFormatterConfig,
    )

    event_daemon_collector = ConfigDescriptor(
        Namespace,
        config=EventCollectorConfig,
    )


def _load_partial_config(cls, root_name, filepath):
    """ Try to load a given config into a config class `cls`. """
    config = cls()
    if filepath:
        config.load_dict(loader.read_config(filepath))
    else:
        loader.read(config, root_name)
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
