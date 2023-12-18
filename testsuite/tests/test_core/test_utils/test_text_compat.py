# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.text_compat`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.utils import text_compat

ENCODING = text_compat.DEFAULT_ENCODING

TEXT = "blåbærsaft"
BYTES = TEXT.encode(ENCODING)
NATIVE = BYTES if str is bytes else TEXT

NONSTRING = [-3.14, None, True, (1, 0), object()]


# text_compat.to_str

def test_text_to_str():
    """ PY2 unicode text to native string. """
    assert text_compat.to_str(TEXT, ENCODING) == NATIVE


def test_bytes_to_str():
    """ PY3 bytestring to native string. """
    assert text_compat.to_str(BYTES, ENCODING) == NATIVE


@pytest.mark.parametrize("value", NONSTRING)
def test_obj_to_str(value):
    assert text_compat.to_str(value, ENCODING) == str(value)


# text_compat.to_text

def test_bytes_to_text():
    assert text_compat.to_text(BYTES, ENCODING) == TEXT


def test_text_to_text():
    assert text_compat.to_text(TEXT, ENCODING) == TEXT


@pytest.mark.parametrize("value", NONSTRING)
def test_obj_to_text(value):
    assert text_compat.to_text(value, ENCODING) == six.text_type(value)


# text_compat.to_bytes

def test_bytes_to_bytes():
    assert text_compat.to_bytes(BYTES, ENCODING) == BYTES


def test_text_to_bytes():
    assert text_compat.to_bytes(TEXT, ENCODING) == BYTES


@pytest.mark.parametrize("value", NONSTRING)
def test_obj_to_bytes(value):
    byte_value = six.text_type(value).encode("utf-8")
    assert text_compat.to_bytes(value, ENCODING) == byte_value
