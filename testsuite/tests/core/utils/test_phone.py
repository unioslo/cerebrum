# -*- coding: utf-8 -*-
"""
Unit tests for mod:`Cerebrum.utils.phone`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import phonenumbers
import pytest

from Cerebrum.utils import phone


def _get_type_id(value):
    return type(value).__name__


@pytest.mark.parametrize(
    "value",
    ["123", "123".encode("ascii")],
    ids=_get_type_id,
)
def test_valid_type(value):
    phone.parse(value, region="NO")


@pytest.mark.parametrize(
    "value",
    [None, True, (), [], {}, object()],
    ids=_get_type_id,
)
def test_invalid_type(value):
    with pytest.raises(phone.NumberParseException):
        phone.parse(value)


def test_too_short():
    expect_type = phone.NumberParseException.NOT_A_NUMBER
    with pytest.raises(phone.NumberParseException) as excinfo:
        phone.parse("")
    assert excinfo.value.error_type == expect_type


def test_too_long():
    expect_type = phone.NumberParseException.TOO_LONG
    with pytest.raises(phone.NumberParseException) as excinfo:
        phone.parse("0" * 42, region="NO")
    assert excinfo.value.error_type == expect_type


def test_no_country_code():
    expect_type = phone.NumberParseException.INVALID_COUNTRY_CODE
    with pytest.raises(phone.NumberParseException) as excinfo:
        phone.parse("123", region=None)
    assert excinfo.value.error_type == expect_type


def test_parse_return_value():
    numobj = phone.parse("123", region="NO")
    assert isinstance(numobj, phone.PhoneNumber)


def test_region():
    country_code = phonenumbers.country_code_for_region("GB")
    numobj = phone.parse("123", region="GB")
    assert numobj.country_code == country_code


@pytest.mark.parametrize(
    "value",
    [True, (), [], {}, object()],
    ids=_get_type_id,
)
def test_invalid_region_type(value):
    with pytest.raises((TypeError, phone.NumberParseException)):
        phone.parse("123", region=value)


@pytest.mark.parametrize("invalid_region", ["", "a", "no", "gb", "NOR", "ABC"])
def test_invalid_region_value(invalid_region):
    expect_type = phone.NumberParseException.INVALID_COUNTRY_CODE
    with pytest.raises(phone.NumberParseException) as excinfo:
        phone.parse("123", region=invalid_region)
    assert excinfo.value.error_type == expect_type


def test_unknown_region():
    expect_type = phone.NumberParseException.INVALID_COUNTRY_CODE
    with pytest.raises(phone.NumberParseException) as excinfo:
        phone.parse("123", region="XX")
    assert excinfo.value.error_type == expect_type


def test_country_code_overrides_region():
    country_code = phonenumbers.country_code_for_region("NO")
    number = "+{} {}".format(country_code, "123")
    numobj = phone.parse(number, region="GB")
    assert numobj.country_code == country_code


def test_equality():
    assert phone.parse("123", region="NO") == phone.parse("123", region="NO")
    assert phone.parse("123", region="NO") != phone.parse("456", region="NO")


def test_object_equality():
    numobj = phone.parse("123", region="NO")
    assert numobj == numobj


def test_repr():
    numobj = phone.parse("+47 123")
    s = repr(numobj)
    # we don't particularly care about the formatting:
    # as long as the information is there it's OK
    assert type(numobj).__name__ in s
    assert "country_code=47" in s
    assert "national_number=123" in s


@pytest.mark.parametrize("country_code,region",
                         [("+47", "NO"), ("0047", "NO")])
def test_country_code_formats(country_code, region):
    numobj = phone.parse("{} {}".format(country_code, "123"), region=region)
    assert numobj.country_code == phonenumbers.country_code_for_region(region)


@pytest.mark.parametrize(
    "value",
    [True, (), [], {}, object()],
    ids=_get_type_id,
)
def test_is_valid_invalid_type(value):
    with pytest.raises(AttributeError):
        phone.is_valid(value)


# interestingly, emergency service numbers are considered invalid
@pytest.mark.parametrize(
    "number,region",
    [
        ("110", "NO"),
        ("112", "NO"),
        ("113", "NO"),
        ("999", "GB"),
    ],
)
def test_invalid_number(number, region):
    numobj = phone.parse(number, region=region)
    assert not phone.is_valid(numobj)


@pytest.mark.parametrize("number,region", [
    ("22 85 50 50", "NO"),
    ("+47 22 85 50 50", "NO"),
    ("0047 22 85 50 50", "NO"),
    ("+ 4 7 228 5   5-05.0", "NO"),
    ("0300 200 3310", "GB"),
    ("+44 300 200 3310", "GB"),
])
def test_valid_number(number, region):
    numobj = phone.parse(number, region=region)
    assert phone.is_valid(numobj)


def test_default_format():
    numobj = phone.parse("22 85 50 50", region="NO")
    assert phone.format(numobj) == "+4722855050"


@pytest.mark.parametrize("number,region,expected_formatting", [
    ("22 85 50 50", "NO", "+4722855050"),
    ("0300 200 3310", "GB", "+443002003310"),
])
def test_format_e164(number, region, expected_formatting):
    numobj = phone.parse(number, region=region)
    assert phone.format(numobj, format=phone.E164) == expected_formatting


@pytest.mark.parametrize("number,region,expected_formatting", [
    ("22 85 50 50", "NO", "+47 22 85 50 50"),
    ("0300 200 3310", "GB", "+44 300 200 3310"),
])
def test_format_international(number, region, expected_formatting):
    numobj = phone.parse(number, region=region)
    value = phone.format(numobj, format=phone.INTERNATIONAL)
    assert value == expected_formatting


@pytest.mark.parametrize("number,region,expected_formatting", [
    ("22 85 50 50", "NO", "22 85 50 50"),
    ("0300 200 3310", "GB", "0300 200 3310"),
])
def test_format_national(number, region, expected_formatting):
    numobj = phone.parse(number, region=region)
    assert phone.format(numobj, format=phone.NATIONAL) == expected_formatting


@pytest.mark.parametrize("number,region,expected_formatting", [
    ("22 85 50 50", "NO", "tel:+47-22-85-50-50"),
    ("0300 200 3310", "GB", "tel:+44-300-200-3310"),
])
def test_format_rfc3966(number, region, expected_formatting):
    numobj = phone.parse(number, region=region)
    assert phone.format(numobj, format=phone.RFC3966) == expected_formatting


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize("country_code,primary_region", [
    (44, "GB"),
    (47, "NO"),
])
def test_country2region(country_code, primary_region):
    # intentionally only tests the first (primary) region.
    # since these lists can grow and we don't want to maintain
    # an accurate source of truth in this interface.
    assert primary_region in phone.country2region(country_code)


@pytest.mark.filterwarnings("ignore")
def test_country2region_unknown_country_code():
    assert len(phone.country2region(0)) == 0
