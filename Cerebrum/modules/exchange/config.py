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
""" This module defines all necessary config for the Exchange integration. """

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)

from Cerebrum.config.loader import read, read_config

from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      Iterable,
                                      String)


class ExchangeClientConfig(Configuration):
    u"""Configuration for the Exchange client."""
    mock = ConfigDescriptor(
        Boolean,
        default=False,
        doc=u"Use mock client")

    auth_user = ConfigDescriptor(
        String,
        default=u"cereauth",
        doc=u"User to authenticate with WinRM")

    auth_user_domain = ConfigDescriptor(
        String,
        default=u".",
        doc=u"Domain the authentication user resides in")

    exchange_admin = ConfigDescriptor(
        String,
        default=u"exchange_admin",
        doc=u"The user authorized to call Exchange-related commands")

    exchange_admin_domain = ConfigDescriptor(
        String,
        default=u".",
        doc=u"Domain the exchange admin user resides in")

    domain_reader = ConfigDescriptor(
        String,
        default=u"cerebrum_exchange_reader",
        doc=u"Account that can read from AD")

    domain_reader_domain = ConfigDescriptor(
        String,
        default=u".",
        doc=u"Domain the account reading from AD resides in")

    management_host = ConfigDescriptor(
        String,
        default=None,
        doc=u"The hostname which management operations can be run on")

    secondary_management_host = ConfigDescriptor(
        String,
        default=None,
        doc=u"The hostname which Connect-ExchangeServer connects to")

    jumphost = ConfigDescriptor(
        String,
        default=None,
        doc=u"The WinRM jumphost used for connecting to the management server")

    jumphost_port = ConfigDescriptor(
        Integer,
        default=5986,
        doc=u"Port to connect to")

    exchange_commands = ConfigDescriptor(
        Iterable,
        default=[],
        doc=u"A map of specialized commands")

    ca = ConfigDescriptor(
        String,
        default=None,
        doc=u"Certificate authority of the jumphost")

    client_key = ConfigDescriptor(
        String,
        default=None,
        doc=u"Path to clients private certificate")

    client_cert = ConfigDescriptor(
        String,
        default=None,
        doc=u"Path to clients cert file")

    hostname_verification = ConfigDescriptor(
        Boolean,
        default=True,
        doc=u"Check for hostname match in certificate")

    enabled_encryption = ConfigDescriptor(
        Boolean,
        default=True,
        doc=u"Communicate via TLS")

    mailbox_path = ConfigDescriptor(
        String,
        default=None,
        doc=u"Path for mailbox placements")

    group_ou = ConfigDescriptor(
        String,
        default=None,
        doc=u"OU groups should reside in")


class ExchangeSelectionCriteria(Configuration):
    mailbox_spread = ConfigDescriptor(
        String,
        default=u"exchange_account",
        doc=u"The spread to select target accounts to Exchange by")

    group_spread = ConfigDescriptor(
        String,
        default=u"exchange_group",
        doc=u"The spread to select target groups for Exchange by")

    shared_mbox_spread = ConfigDescriptor(
        String,
        default=u"exch_shared_mbox",
        doc=u"The spread to select target shared mailboxes for Exchange by")

    ad_spread = ConfigDescriptor(
        String,
        default=u"AD_account",
        doc=u"Filter criteria for accounts")

    group_name_translations = ConfigDescriptor(
        Iterable,
        default=[],
        doc=u"Map of group name translations")

    randzone_publishment_group = ConfigDescriptor(
        String,
        default=None,
        doc=u"Mempership in this group denotes publishment "
            "in address book for randzone users")


class ExchangeEventCollectorConfig(Configuration):
    u"""Configuration for the Exchange event collector."""
    run_interval = ConfigDescriptor(
        Integer,
        minval=1,
        default=180,
        doc=u'How often (in seconds) we run notification')

    failed_limit = ConfigDescriptor(
        Integer,
        minval=1,
        default=10,
        doc=u'How many times we retry an event')

    failed_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=20*60,
        doc=(u'How long (seconds) should we wait before processesing the '
             'event again'))

    unpropagated_delay = ConfigDescriptor(
        Integer,
        minval=1,
        default=90*60,
        doc=(u'How old (seconds) should an event not registered as '
             'processesed be before we enqueue it'))


class ExchangeHandlerConfig(Configuration):
    u"""Configuration for the event handler."""
    handler_class = ConfigDescriptor(
        String,
        default=u"ExchangeEventHandler",
        doc=u"Handler class used for processing events")

    handler_mod = ConfigDescriptor(
        String,
        default=u"Cerebrum.modules.no.uio.exchange.consumer",
        doc=u"Handler module used for processing events")


class DeferredExchangeHandlerConfig(Configuration):
    u"""Configuration for the defered event handler."""
    handler_class = ConfigDescriptor(
        String,
        default=None,
        doc=u"Deferred handler class used for processing events")

    handler_mod = ConfigDescriptor(
        String,
        default=None,
        doc=u"Deferred handler module used for processing events")


class ExchangeConfig(Configuration):
    u"""Configuration for the Exchange integration."""
    client = ConfigDescriptor(
        Namespace,
        config=ExchangeClientConfig)

    selection_criteria = ConfigDescriptor(
        Namespace,
        config=ExchangeSelectionCriteria)

    eventcollector = ConfigDescriptor(
        Namespace,
        config=ExchangeEventCollectorConfig)

    handler = ConfigDescriptor(
        Namespace,
        config=ExchangeHandlerConfig)

    deferred_handler = ConfigDescriptor(
        Namespace,
        config=DeferredExchangeHandlerConfig)


def load_config(filepath=None):
    config_cls = ExchangeConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'exchange')
    config_cls.validate()
    return config_cls
