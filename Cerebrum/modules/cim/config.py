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
""" This module defines all neccessary config for the CIM integration. """

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)

from Cerebrum.config.loader import read, read_config

from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      Setting,
                                      String)


def mixin_config(attr, cls):
    return type('_ConfigMixin',
                (Configuration, ),
                {attr: ConfigDescriptor(Namespace, config=cls,)})


class CIMClientConfig(Configuration):
    """Configuration for the CIM WS client."""
    api_url = ConfigDescriptor(
        String,
        default=None,
        doc="URL to the JSON API. Will be suffixed with endpoints.")

    dry_run = ConfigDescriptor(
        Boolean,
        default=True,
        doc="Send requests to web service with dry run mode enabled?")

    auth_user = ConfigDescriptor(
        String,
        default="webservice",
        doc="Username to use when connecting to the WS.")

    auth_system = ConfigDescriptor(
        String,
        default=None,
        doc="The system name used for the password file, for example 'test'.")

    auth_host = ConfigDescriptor(
        String,
        default="webservice",
        doc="The hostname used for the password file.")


class CIMEventConfig(Configuration):
    """Configuration for the CIM event handler."""
    workers = ConfigDescriptor(
        Integer(minval=1),
        default=1,
        doc=u'Number of workers against CIM')

    channels = ConfigDescriptor(
        Iterable(template=String(minlen=1)),
        default=['CIM'],
        doc=u'Event channel(s)')

    fail_limit = ConfigDescriptor(
        Integer(minval=1),
        default=10,
        doc=u'How many times we retry an event')

    delay_run_interval = ConfigDescriptor(
        Integer(minval=1),
        default=180,
        doc=u'How often (in seconds) we run notification')
    
    delay_event_timeout = ConfigDescriptor(
        Integer(minval=1),
        default=90*60,
        doc=(u'How old (seconds) should an event not registred as '
             'processesed be before we enqueue it'))

    delay_failed = ConfigDescriptor(
        Integer(minval=1),
        default=20*60,
        doc=(u'How long (seconds) should we wait before processesing the '
             'event again'))


class CIMConfig(
        mixin_config('client', CIMClientConfig),
        mixin_config('event', CIMEventConfig),
        Configuration):
    pass


def load_config(filepath=None):
    config_cls = CIMConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'cim')
    config_cls.validate()
    return config_cls
