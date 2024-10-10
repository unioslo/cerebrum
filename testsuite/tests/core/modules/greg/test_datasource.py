# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.greg.datasource` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.greg import datasource
from Cerebrum.utils import date as date_utils


#
# test normalize_id
#


VALID_IDS = (
    (" 123\n ", "123"),  # whitespace
    ("0321", "321"),     # zero-prefix
)

INVALID_IDS = ("", None, "\t  \n", "7f")


@pytest.mark.parametrize("value, expect", VALID_IDS,
                         ids=[v[0] for v in VALID_IDS])
def test_normalize_id(value, expect):
    assert datasource.normalize_id(value) == expect


@pytest.mark.parametrize("value", INVALID_IDS)
def test_normalize_id_invalid(value):
    with pytest.raises(Exception) as exc_info:
        datasource.normalize_id(value)
    assert six.text_type(exc_info.value)


#
# test parse_greg_date
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
def test_parse_greg_date(value, expect):
    assert datasource.parse_greg_date(value) == expect


@pytest.mark.parametrize("value", INVALID_DATES)
def test_parse_greg_date_invalid(value):
    with pytest.raises(ValueError):
        datasource.parse_greg_date(value)


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_greg_date_allow_empty(value):
    assert datasource.parse_greg_date(value, True) is None


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_greg_date_disallow_empty(value):
    with pytest.raises(ValueError) as exc_info:
        datasource.parse_greg_date(value)
    error = six.text_type(exc_info.value)
    assert error == "empty date"


#
# test parse_greg_dt
#


def test_parse_greg_dt():
    value = "2024-09-26T10:57:55.500000Z"
    expect = date_utils.apply_timezone(
        datetime.datetime(2024, 9, 26, 10, 57, 55, 500000),
        date_utils.UTC,
    )
    assert datasource.parse_greg_dt(value) == expect


@pytest.mark.parametrize("value", ["foo", "2024-02-30T10:57:55.500000Z"])
def test_parse_greg_dt_invalid(value):
    with pytest.raises(ValueError):
        datasource.parse_greg_dt(value)


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_greg_dt_allow_empty(value):
    assert datasource.parse_greg_dt(value, True) is None


@pytest.mark.parametrize("value", EMPTY_DATES)
def test_parse_greg_dt_disallow_empty(value):
    with pytest.raises(ValueError) as exc_info:
        datasource.parse_greg_dt(value)
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


def test_parse_message():
    assert datasource.parse_message(
        """
        {
            "id": 100,
            "source": "greg:example:test",
            "type": "person_role.add",
            "version": 1,
            "data": {
                "person_id": 1,
                "role_id": 2,
                "example": "hello"
            }
        }
        """
    ) == {
        'id': "100",
        'source': "greg:example:test",
        'type': "person_role.add",
        'data': {
            'person_id': "1",
            'role_id': "2",
            'example': "hello",
        },
    }


def test_parse_message_invalid():
    with pytest.raises(Exception):
        datasource.parse_message(
            """
            {
                "id": 100,
                "source": "",
                "type": "person_role.add",
            }
            """
        )


#
# test parse_orgunit
#


def test_parse_orgunit():
    assert datasource.parse_orgunit({
        'active': True,
        'created': "2021-12-03T12:05:23.000000Z",
        'deleted': False,
        'id': 3,
        'identifiers': [
            {
                'id': 1,
                'source': "orgreg",
                'name': "orgreg_id",
                'value': "3",
            },
            {
                'id': 2,
                'source': "sapuio",
                'name': "legacy_stedkode",
                'value': "123456",
            },
        ],
        'name_en': "Example Location",
        'name_nb': "Eksempelsted",
        'parent': 2,
        'updated': '2024-09-26T10:57:55.500000Z',
    }) == {
        'id': "3",
        'parent': "2",
        'active': True,
        'identifiers': (
            {
                'source': "orgreg",
                'name': "orgreg_id",
                'value': "3",
            },
            {
                'source': "sapuio",
                'name': "legacy_stedkode",
                'value': "123456",
            },
        ),
    }


#
# test parse_orgunit
#


def test_parse_person():
    assert datasource.parse_person({
        'id': 2,
        'first_name': "John",
        'last_name': "Doe",
        'date_of_birth': "1998-06-28",
        'gender': "male",
        'meta': None,
        'registration_completed_date': "2021-11-23",
        'created': "2021-12-03T12:05:23.000000Z",
        'updated': "2022-02-22T11:31:27.000000Z",
        'identities': [
            {
                'id': 6,
                'created': "2021-12-20T12:38:24.291923Z",
                'updated': "2021-12-20T12:38:24.291943Z",
                'person': 2,
                'source': "example",
                'type': "feide_id",
                'value': "foo@example.org",
                'invalid': None,
                'verified': "manual",
                'verified_at': "2020-12-12T00:00:00Z",
                'verified_by': 2,
            },
            {
                'id': 9,
                'created': "2021-12-03T12:05:23.130497Z",
                'updated': "2021-12-03T13:11:06.356517Z",
                'person': 2,
                'source': "example",
                'type': "passport_number",
                'value': "NO-123456789",
                'invalid': None,
                'verified': "manual",
                'verified_at': "2021-11-02T12:05:23Z",
                'verified_by': 2,
            }
        ],
        'roles': [{
            'id': 32,
            'start_date': "2021-11-03",
            'end_date': "2022-02-21",
            'sponsor': 2,
            'type': "guest-researcher",
            'available_in_search': False,
            'comments': "",
            'contact_person_unit': "",
            'created': "2021-12-03T12:05:23.117311Z",
            'updated': "2022-02-22T11:31:27.855737Z",
            'orgunit': {
                'active': True,
                'created': "2021-12-03T12:05:23.000000Z",
                'deleted': False,
                'id': 3,
                'identifiers': [
                    {
                        'id': 1,
                        'source': "orgreg",
                        'name': "orgreg_id",
                        'value': "3",
                    },
                    {
                        'id': 2,
                        'source': "sapuio",
                        'name': "legacy_stedkode",
                        'value': "123456",
                    },
                ],
                'name_en': "Example Location",
                'name_nb': "Eksempelsted",
                'parent': 2,
                'updated': '2024-09-26T10:57:55.500000Z',
            },
        }],
        'consents': [{
            'choice': "no",
            'consent_given_at': "2022-01-21",
            'id': 6,
            'type': {
                'identifier': "publish",
                'mandatory': True,
            },
        }],
    }) == {
        'id': "2",
        'first_name': "John",
        'last_name': "Doe",
        'date_of_birth': datetime.date(1998, 6, 28),
        'registration_completed_date': datetime.date(2021, 11, 23),
        'identities': (
            {
                'id': "6",
                'person': "2",
                'source': "example",
                'type': "feide_id",
                'value': "foo@example.org",
                'verified': "manual",
            },
            {
                'id': "9",
                'person': "2",
                'source': "example",
                'type': "passport_number",
                'value': "NO-123456789",
                'verified': "manual",
            },
        ),
        'roles': (
            {
                'id': "32",
                'type': "guest-researcher",
                'start_date': datetime.date(2021, 11, 3),
                'end_date': datetime.date(2022, 2, 21),
                'orgunit': {
                    'id': "3",
                    'parent': "2",
                    'active': True,
                    'identifiers': (
                        {
                            'source': "orgreg",
                            'name': "orgreg_id",
                            'value': "3",
                        },
                        {
                            'source': "sapuio",
                            'name': "legacy_stedkode",
                            'value': "123456",
                        },
                    ),
                },
            },
        ),
        'consents': (
            {
                'type': "publish",
                'value': "no",
            },
        ),
    }
