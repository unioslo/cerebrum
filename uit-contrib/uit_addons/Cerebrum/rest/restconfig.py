#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import cereconf

DEBUG = True

PORT = 8800
HOST = 'localhost'

APPNAME = u"cerebrum-rest"

# map from a file with lines like:
#     username:key
# to a dict like:
#     {'key': 'username'}
#keyfile = '/cerebrum/etc/passwords/api.cerebrum.uio.no/client_api_keys/keys'
keyfile = '/home/cerebrum/cerebrum/Cerebrum/rest/backend_key'
with open(keyfile) as f:
    lines = [x.split(':') for x in f.read().splitlines() if len(x)]
    print lines
    apikeys = dict(map(reversed, lines))
    assert all([len(key) > 20 for key in apikeys.keys()])


AUTH = [
    {
        'name': 'HeaderAuth',
        'header': 'X-API-Key',
        'keys': apikeys,
    },
    # {
    #     'name': 'BasicAuth',
    #     'realm': cereconf.INSTITUTION_DOMAIN_NAME,
    #     'challenge': True,
    #     'whitelist': [],
    # },
    # {
    #     'name': 'CertAuth',
    #     'certs': {
    #         'certificate-fingerprint': 'bootstrap_account',
    #     }
    # },
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'fmt': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'fmt',
            'filename': '/cerebrum/var/log/cerebrum/restapi.log',
            'encoding': 'UTF-8'
        },
    },
    'loggers': {
        '': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    }
}
