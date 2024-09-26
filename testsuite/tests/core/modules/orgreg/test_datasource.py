# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.orgreg.datasource` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.orgreg import datasource


#
# test parse_orgreg_date
#


VALID_DATES = (
    ("2024-09-10", datetime.date(2024, 9, 10)),
    ("2024-W37-2", datetime.date(2024, 9, 10)),
)

INVALID_DATES = (
    "foo",
    "2024-02-30",
)

EMPTY_DATES = ("", None, "\t  \n")


@pytest.mark.parametrize("value,expect", VALID_DATES,
                         ids=[v[0] for v in VALID_DATES])
def test_parse_orgreg_date(value, expect):
    assert datasource.parse_orgreg_date(value) == expect


@pytest.mark.parametrize("value", INVALID_DATES)
def test_parse_orgreg_date_invalid(value):
    with pytest.raises(ValueError):
        datasource.parse_orgreg_date(value)


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_orgreg_date_allow_empty(value):
    assert datasource.parse_orgreg_date(value, True) is None


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_orgreg_date_disallow_empty(value):
    with pytest.raises(ValueError) as exc_info:
        datasource.parse_orgreg_date(value)
    error = six.text_type(exc_info.value)
    assert error == "empty date"


#
# test normalize_text
#


EXAMPLE_TEXT = (
    ("   strip whitespace  \n", "strip whitespace"),
    ("NFD-to-NFC A\N{COMBINING RING ABOVE}",
     "NFD-to-NFC \N{LATIN CAPITAL LETTER A WITH RING ABOVE}"),
)

EMPTY_TEXT = ("", None, "\t  \n")


@pytest.mark.parametrize("value,expect", EXAMPLE_TEXT,
                         ids=[v[1] for v in EXAMPLE_TEXT])
def test_normalize_text(value, expect):
    assert datasource.normalize_text(value) == expect


@pytest.mark.parametrize("value", EMPTY_TEXT)
def test_normalize_text_allow_empty(value):
    assert datasource.normalize_text(value, True) is None


@pytest.mark.parametrize("value", EMPTY_TEXT)
def test_normalize_text_disallow_empty(value):
    with pytest.raises(ValueError) as exc_info:
        datasource.normalize_text(value)
    error = six.text_type(exc_info.value)
    assert error == "empty text"


#
# test parse_orgreg_address
#


def test_parse_orgreg_address_empty():
    assert datasource.parse_orgreg_address({}) is None


def test_parse_orgreg_address_empty_ish():
    assert datasource.parse_orgreg_address({'street': "   "}) is None


def test_parse_orgreg_address_partial():
    assert datasource.parse_orgreg_address({
        'city': " ",
        'country': "UK",
    }) == {
        'street': None,
        'extended': None,
        'postalCode': None,
        'city': None,
        'country': "UK",
    }


def test_parse_orgreg_address_full():
    assert datasource.parse_orgreg_address({
        'street': "Example Street 1\n",
        'extended': "  c/o John Smith",
        'postalCode': "0123",
        'city': "Example Town",
        'country': "UK",
        'province': "Exampleshire",
    }) == {
        'street': "Example Street 1",
        'extended': "c/o John Smith",
        'postalCode': "0123",
        'city': "Example Town",
        'country': "UK",
    }


#
# test parse_orgreg_address
#


def test_parse_localized_data_empty():
    assert datasource.parse_localized_data({}) == {
        'en': None,
        'nb': None,
        'nn': None,
    }


def test_parse_localized_data_empty_ish():
    assert datasource.parse_localized_data({
        'eng': "  ",
    }) == {
        'en': None,
        'nb': None,
        'nn': None,
    }


def test_parse_localized_data_omit_unknown():
    assert datasource.parse_localized_data({
        'eng': "hello",
        'nob': "hei",
        'swe': "hej",
    }) == {
        'en': "hello",
        'nb': "hei",
        'nn': None,
    }


#
# test parse_external_id
#


@pytest.mark.parametrize(
    "value",
    (
        {},
        {'type': "foo", 'sourceSystem': "bar"},
        {'type': "\t", 'sourceSystem': "foo", 'value': "bar"},
        {'type': "foo", 'sourceSystem': "  ", 'value': "bar"},
        {'type': "foo", 'sourceSystem': "bar", 'value': "\n"},
    ),
)
def test_parse_external_id_invalid(value):
    with pytest.raises((KeyError, ValueError)):
        datasource.parse_external_id(value)


def test_parse_external_id():
    assert datasource.parse_external_id({
        'type': "foo",
        'sourceSystem': "bar",
        'value': "baz",
    }) == {
        'type': "foo",
        'sourceSystem': "bar",
        'value': "baz",
    }


def test_parse_external_id_omit_unknown():
    assert datasource.parse_external_id({
        'type': "foo",
        'sourceSystem': "bar",
        'value': "baz",
        'something_extra': "",
    }) == {
        'type': "foo",
        'sourceSystem': "bar",
        'value': "baz",
    }
