# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.bofhd.session """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
from six.moves import xmlrpc_client

from Cerebrum.modules.bofhd import xmlutils
from Cerebrum.utils import date as date_utils


def test_none_to_xmlrpc():
    assert xmlutils.native_to_xmlrpc(None) == ":None"


def test_none_to_native():
    assert xmlutils.xmlrpc_to_native(":None") is None


#
# Identity tests - values that should be returned as-is both ways
#
IDENTITY_TESTS = [
    # ID,  VALUE
    ("text", "hello world"),
    ("int", 127),
    ("float", 3.1415926),
    ("list", ["foo", 3]),
    ("tuple", ("foo", 3)),
    ("dict", {"a": 1, 3: "b"}),
]


@pytest.mark.parametrize(
    "value",
    [t[1] for t in IDENTITY_TESTS],
    ids=[t[0] for t in IDENTITY_TESTS],
)
def test_xmlrpc_is_native(value):
    """ xmlrpc == native """
    assert xmlutils.xmlrpc_to_native(value) == value
    assert xmlutils.native_to_xmlrpc(value) == value


#
# Mirror tests - values that should map to each other in either direction
#
# hashlib.md5(b"hello world").digest()
binary_data = b'^\xb6;\xbb\xe0\x1e\xee\xd0\x93\xcb"\xbb\x8fZ\xcd\xc3'


MIRRORED_TESTS = [
    # ID, NATIVE, XMLRPC
    ("binary", bytearray(binary_data), xmlrpc_client.Binary(data=binary_data)),
    ("esctext", ":something", "::something"),
]


@pytest.mark.parametrize(
    "native, xmlrpc",
    [t[1:3] for t in MIRRORED_TESTS],
    ids=[t[0] for t in MIRRORED_TESTS],
)
def test_xmlrpc_mirrors_native(native, xmlrpc):
    """ native <-> xmlrpc are mirrored values. """
    assert xmlutils.native_to_xmlrpc(native) == xmlrpc
    assert xmlutils.xmlrpc_to_native(xmlrpc) == native


ascii_text = "hello world!"
ascii_bytes = ascii_text.encode("ascii")


def test_bytes_to_xmlrpc():
    """ bytes are considered ascii text. """
    assert xmlutils.native_to_xmlrpc(ascii_bytes) == ascii_text


def test_bytes_to_native():
    """ bytes are considered ascii text. """
    assert xmlutils.xmlrpc_to_native(ascii_bytes) == ascii_text


def test_normalize_xmlrpc_to_native():
    """ text input is normalized. """
    input_text = "BLA\N{COMBINING RING ABOVE}BÆR"
    norm_text = "BL\N{LATIN CAPITAL LETTER A WITH RING ABOVE}BÆR"
    assert xmlutils.xmlrpc_to_native(input_text) == norm_text


def test_naive_datetime_to_xmlrpc():
    """ convert a naive datetime to xmlrpc-repesentation in local time """
    dt = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654)
    xmldt = xmlutils.native_to_xmlrpc(dt)
    # A naive datetime is assumed to already be in local time
    assert xmldt.value == '19980628T23:30:11'


@pytest.mark.skipif(
    date_utils.TIMEZONE.zone != "Europe/Oslo",
    reason="Test only works with cereconf.TIMEZONE set to Europe/Oslo",
)
def test_tz_aware_datetime_to_xmlrpc():
    """ convert a tz-aware datetime to xmlrpc-repesentation in local time """
    dt = date_utils.apply_timezone(
        datetime.datetime(1998, 6, 28, 23, 30, 11, 987654),
        date_utils.UTC)
    xmldt = xmlutils.native_to_xmlrpc(dt)
    # Datetime in UTC - must be converted to local time.
    assert xmldt.value == '19980629T01:30:11'


def test_date_to_xmlrpc():
    """ convert a date to xmlrpc-repesentation in local time """
    dt = datetime.date(1998, 6, 28)
    xmldt = xmlutils.native_to_xmlrpc(dt)
    assert xmldt.value == '19980628T00:00:00'
