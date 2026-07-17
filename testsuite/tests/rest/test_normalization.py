#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests that string/unicode input to the REST API gets normalized. """

from __future__ import unicode_literals

from Cerebrum.rest.api import validator

OHM_SIGN = '\N{OHM SIGN}'
LETTER_OMEGA = '\N{GREEK CAPITAL LETTER OMEGA}'


def test_string_validator_normalizes_unicode():
    assert validator.String()(OHM_SIGN) == LETTER_OMEGA


def test_url_mapper_normalizes_unicode(app):
    converters = app.url_map.converters
    assert converters['default'].__name__ == 'NormalizedUnicodeConverter'
    assert converters['string'].__name__ == 'NormalizedUnicodeConverter'
    adapter = app.url_map.bind('localhost', '/')
    match = adapter.match('/v1/accounts/' + OHM_SIGN)
    assert match == ('api_v1.account', {'name': LETTER_OMEGA})
