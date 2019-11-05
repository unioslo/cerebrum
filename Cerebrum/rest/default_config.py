#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import cereconf

DEBUG = True

# Enabling DRYRUN will rollback all database transactions after a request
DRYRUN = False

PORT = 8000
HOST = 'localhost'

APPNAME = 'cerebrum-rest'

# Disable 404 suggestions from flask-restplus
ERROR_404_HELP = False

AUTH = [
    # {
    #     'name': 'CertAuth',
    #     'certs': {
    #         '1a56e3bfd0a0974110894a73fa2ad31897dbf76d': 'bootstrap_account',
    #     }
    # },
    {
        'name': 'BasicAuth',
        'realm': cereconf.INSTITUTION_DOMAIN_NAME,
        'whitelist': ['bootstrap_account'],
    },
    # {
    #     'name': 'HeaderAuth',
    #     'header': 'X-API-Key',
    #     'keys': {
    #         'secret-key': 'username',
    #     },
    # },
]
