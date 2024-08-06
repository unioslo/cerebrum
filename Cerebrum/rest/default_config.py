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
Default config for the `Cerebrum.rest` API.

The actual config is imported from a `restconfig` module.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import cereconf


#
# Debug mode - see Flask docs for details
#
DEBUG = False

#
# Drydun - disable database commits
#
DRYRUN = False

#
# Default interface and port for dev servers
#
HOST = "localhost"
PORT = 8000

#
# Flask application name
#
APPNAME = "cerebrum-rest"

#
# Disable 404 suggestions from flask-restplus
#
ERROR_404_HELP = False

#
# Cerebrum API authentication mechanism
#
# Each enabled mechanism will try to validate request input and map it to an
# account.  If no mechanism is enabled, or no mechanism can validate a given
# request, it will be rejected.
#
AUTH = [
    # HeaderAuth - authenticate using hard-coded header values.  Typically only
    # useful in dev setups:
    #
    #   curl -H 'X-Key: example' ...
    #
    # {
    #     'name': "HeaderAuth",
    #     'header': "X-Key",
    #     'keys': {
    #         # Valid header values, and which acocunt they should map to
    #         # 'example': cereconf.INITIAL_ACCOUNTNAME,
    #     },
    # },

    # BasicAuth - authenticate using username and passwords of actual accounts.
    # Note that only whitelisted accounts can authenticate this way.
    #
    {
        'name': 'BasicAuth',
        'realm': cereconf.INSTITUTION_DOMAIN_NAME,
        'whitelist': [
            # cereconf.INITIAL_ACCOUNTNAME,
        ],
    },

    # ApiSubscriptionAuth - authenticate using the `Cerebrum.modules.apikeys`
    # module.  This is used in production setups, along with *PROXY_AUTH*.
    #
    # {
    #     'name': "ApiSubscriptionAuth",
    #     'header': "X-Api-Subscription",
    # },
]


# Basic auth for reverse proxy
#
# Some `AUTH` mechanisms requires us to *trust* headers from reverse proxies.
# In these cases we would usually want the proxy authenticate itself.
#
# If `PROXY_AUTH['enable']` is set, *all* calls to the API will require Basic
# auth with the provided username and realm before regular auth is performed.
# The proxy username and password is validated against a known username and
# password in `cereconf.DB_AUTH_DIR`.
#
PROXY_AUTH = {
    'enable': False,
    'username': "",
    'realm': "",
}

#
# Trusted hosts
# A list of known reverse-proxy IPs that we trust to set IP forwarding headers
# correctly.  These IPs will be omitted from logs.
#
TRUSTED_HOSTS = []
