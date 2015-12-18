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
""" This module defines all necessary config for the CIM integration. """

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration,
                                           Namespace)

from Cerebrum.config.loader import read, read_config

from Cerebrum.config.settings import (Boolean,
                                      Integer,
                                      String,
                                      Iterable,
                                      NotSet)


class CIMClientConfig(Configuration):
    u"""Configuration for the CIM WS client."""
    api_url = ConfigDescriptor(
        String,
        default=u"https://localhost/test/_webservices/system/rest/person/1.0/",
        doc=u"URL to the JSON API. Will be suffixed with endpoints.")

    commit = ConfigDescriptor(
        Boolean,
        default=True,
        doc=u"Should requests sent to the web service be committed?")

    auth_user = ConfigDescriptor(
        String,
        default=u"webservice",
        doc=u"Username to use when connecting to the WS.")

    auth_system = ConfigDescriptor(
        String,
        default=None,
        doc=u"The system name used for the password file, for example 'test'.")

    auth_host = ConfigDescriptor(
        String,
        default=u"webservice",
        doc=u"The hostname used for the password file.")


class CIMPhoneMappingConfig(Configuration):
    u"""Configuration for the CIM data source phone mappings."""
    job_mobile = ConfigDescriptor(
        String,
        default=u"MOBILE",
        doc=u'Contact info constant for job mobile')

    job_phone = ConfigDescriptor(
        String,
        default=u"PHONE",
        doc=u'Contact info constant for job phone')

    private_mobile = ConfigDescriptor(
        String,
        default=u"PRIVATEMOBILE",
        doc=u'Contact info constant for private mobile')

    private_phone = ConfigDescriptor(
        String,
        default=u"PRIVPHONE",
        doc=u'Contact info constant for private phone')


class CIMDataSourceConfig(Configuration):
    u"""Configuration for the CIM data source."""
    authoritative_system = ConfigDescriptor(
        String,
        default=u"SAP",
        doc=u'Authoritative system to fetch contact information from.')

    ou_perspective = ConfigDescriptor(
        String,
        default=u"SAP",
        doc=u'Perspective to use when fetching OU structure.')

    phone_country_default = ConfigDescriptor(
        String,
        default=u"NO",
        doc=u'Assume this phone region when otherwise unknown.')

    phone_mappings = ConfigDescriptor(
        Namespace,
        config=CIMPhoneMappingConfig)

    company_hierarchy = ConfigDescriptor(
        Iterable,
        template=String(),
        default=['company',
                 'department',
                 'subdep1',
                 'subdep2',
                 'subdep3',
                 'subdep4',
                 'subdep5',
                 'subdep6',
                 'subdep7',
                 'subdep8',
                 'subdep9',
                 'subdep10',
                 ],
        doc=(u'Hierarchy of field names expected by the CIM web service.'))


class CIMEventCollectorConfig(Configuration):
    u"""Configuration for the CIM event collector."""
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


class CIMConfig(Configuration):
    u"""Configuration for the CIM integration."""
    client = ConfigDescriptor(
        Namespace,
        config=CIMClientConfig)

    datasource = ConfigDescriptor(
        Namespace,
        config=CIMDataSourceConfig)

    eventcollector = ConfigDescriptor(
        Namespace,
        config=CIMEventCollectorConfig)


def load_config(filepath=None):
    config_cls = CIMConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'cim')
    config_cls.validate()
    return config_cls
