#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for SMS utilities. """
from __future__ import print_function, unicode_literals

import pytest


@pytest.fixture
def cereconf(cereconf):
    cereconf.SMS_DISABLED = True
    cereconf.SMS_ACCEPT_REGEX = (r'^\+47\d{8}$', )
    return cereconf


@pytest.fixture
def sms_sender_class(cereconf):
    from Cerebrum.utils.sms import SMSSender
    return SMSSender


@pytest.fixture
def sms_sender(sms_sender_class):
    return sms_sender_class(
        logger=None,
        url='http://localhost/sms/send',
        user='foo',
        system='bar')


class MockResponse(object):

    encoding = 'latin-1'

    def __init__(self, status, text):
        self.status_code = status
        self.text = text

    @property
    def content(self):
        return self.text.encode(self.encoding)


def test_filter_phone_number(sms_sender):
    assert sms_sender._filter_phone_number('+4722855050') == '+4722855050'

    with pytest.raises(ValueError):
        sms_sender._filter_phone_number('bogus')


def test_validate_response(sms_sender):
    good_response = MockResponse(
        200,
        'UT_123¤SENDES¤22855050¤20120322-15:36:35¤¤¤Hello')
    bad_response = MockResponse(
        200,
        'UT_123¤NEINEINEI¤22855050¤20120322-15:36:35¤¤¤Hello')
    bogus_response = MockResponse(400, '!')
    assert sms_sender._validate_response(good_response)
    assert not sms_sender._validate_response(bad_response)
    assert not sms_sender._validate_response(bogus_response)
