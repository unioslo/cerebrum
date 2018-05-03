#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for SMS utilities. """
from __future__ import print_function, unicode_literals

import pytest


@pytest.fixture
def cereconf(cereconf):
    cereconf.SMS_DISABLED = True
    cereconf.SMS_ACCEPT_REGEX = ('^\+47\d{8}$', )
    return cereconf


@pytest.fixture
def sms_sender_class(cereconf):
    from Cerebrum.utils.sms import SMSSender as cls
    return cls


@pytest.fixture
def SMSSender(sms_sender_class):
    return sms_sender_class(
        logger=None,
        url='http://localhost/sms/send',
        user='foo',
        system='bar')


def test_filter_phone_number(SMSSender):
    assert SMSSender._filter_phone_number('+4722855050') == '+4722855050'

    with pytest.raises(ValueError):
        SMSSender._filter_phone_number('bogus')


def test_validate_response(SMSSender):
    class FakeResponse(object):
        def __init__(self, text=None):
            self.text = text

    good_response = FakeResponse(
        'UT_123¤SENDES¤22855050¤20120322-15:36:35¤¤¤Hello')
    bad_response = FakeResponse(
        'UT_123¤NEINEINEI¤22855050¤20120322-15:36:35¤¤¤Hello')
    bogus_response = FakeResponse('!')
    assert SMSSender._validate_response(good_response)
    assert not SMSSender._validate_response(bad_response)
    assert not SMSSender._validate_response(bogus_response)
