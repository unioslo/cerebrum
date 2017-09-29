#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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

from Cerebrum.config.configuration import Configuration, ConfigDescriptor
from Cerebrum.config.loader import read
from Cerebrum.config.settings import String


class ADLDAPConfig(Configuration):
    """Configuration for AD-LDAP connections."""

    ldap_proto = ConfigDescriptor(
        String,
        default=u'ldap',
        doc=u'The protocol to use when connecting to the LDAP-server.'
    )

    ldap_server = ConfigDescriptor(
        String,
        default=u'localhost:389',
        doc=u'The hostname (and port) to connect to.'
    )

    ldap_user = ConfigDescriptor(
        String,
        default=u'cereauth',
        doc=u'The username of the user to bind with.'
    )

    bind_dn_template = ConfigDescriptor(
        String,
        default=u'cn=cereauth,ou=users,dc=ad-example,dc=com',
        doc=u'The DN to use when binding the LDAP connection.'
    )

    users_dn = ConfigDescriptor(
        String,
        default=u'ou=users,dc=ad-example,dc=com',
        doc=u'The DN where to look up users.'
    )

    groups_dn = ConfigDescriptor(
        String,
        default=u'ou=groups,dc=ad-example,dc=com',
        doc=u'The DN where to look up groups.'
    )


def load_ad_ldap_config():
    config = ADLDAPConfig()
    read(config, 'ad_ldap')
    config.validate()
    return config
