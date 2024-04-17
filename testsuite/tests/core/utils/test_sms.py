# -*- coding: utf-8 -*-
""" Unit tests for ``Cerebrum.utils.sms``. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.SMS_DISABLED = True
    cereconf.SMS_ACCEPT_REGEX = (
        r"^\+46\d{7,13}$",
        r"^\+47\d{8}$",
        r"^\d{8}$",
    )
    return cereconf


@pytest.fixture
def sms_sender_class():
    from Cerebrum.utils.sms import SMSSender
    return SMSSender


@pytest.fixture
def sms_sender(sms_sender_class):
    """ An initialized SMSSender """
    return sms_sender_class(
        logger=None,
        url="http://localhost/sms/send",
        user="foo",
        system="bar",
    )


class MockResponse(object):
    """ A mock requests.Response-like object """

    encoding = "latin-1"

    def __init__(self, status, text):
        self.status_code = status
        self.text = text

    @property
    def content(self):
        return self.text.encode(self.encoding)


def test_filter_good_phone_number(sms_sender):
    assert sms_sender._filter_phone_number("+4722855050") == "+4722855050"


def test_filter_bad_phone_number(sms_sender):
    with pytest.raises(ValueError):
        sms_sender._filter_phone_number("+4522855050")


def test_filter_bogus_phone_number(sms_sender):
    with pytest.raises(ValueError):
        sms_sender._filter_phone_number("bogus")


def test_validate_good_response(sms_sender):
    good_response = MockResponse(
        status=200,
        text="UT_123¤SENDES¤22855050¤20120322-15:36:35¤¤¤Hello",
    )
    assert sms_sender._validate_response(good_response)


def test_validate_bad_response(sms_sender):
    bad_response = MockResponse(
        status=200,
        text="UT_123¤NEINEINEI¤22855050¤20120322-15:36:35¤¤¤Hello",
    )
    assert not sms_sender._validate_response(bad_response)


def test_validate_bogus_response(sms_sender):
    bogus_response = MockResponse(
        status=400,
        text="a bogus response",
    )
    assert not sms_sender._validate_response(bogus_response)
