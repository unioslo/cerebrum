# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.greg.mapper` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest

from Cerebrum.modules.greg import mapper


#
# GregOrgunitIds tests
#


def test_get_org_ids():
    get_org_ids = mapper.GregOrgunitIds()
    assert list(
        get_org_ids({
            'id': "1",
            'identifiers': [{
               'source': "orgreg",
               'name': "orgreg_id",
               'value': "1234",
            }],
        })
    ) == [
        ("GREG_OU_ID", "1"),
        ("ORGREG_OU_ID", "1234"),
    ]


#
# get_names tests
#


def test_get_names():
    assert list(
        mapper.get_names({
            'id': "1",
            'first_name': "John",
            'last_name': "Doe",
        })
    ) == [
        ("FIRST", "John"),
        ("LAST", "Doe"),
    ]

#
# GregPersonIds tests
#


class _ExampleIds(mapper.GregPersonIds):
    type_map = {
        ('example', 'foo'): "FOO",
        'bar': "BAR",
        'baz': "BAZ",
    }
    normalize_map = {
        'bar': lambda v: v.lower(),
    }
    verified_values = set(('y',))
    greg_id_type = 'TEST-ID'


def test_get_person_ids():
    get_person_ids = _ExampleIds()
    assert list(
        get_person_ids({
            'id': "1",
            'identities': [
                {
                    'source': "example",
                    'type': "foo",
                    'verified': "y",
                    'value': "Example-Value",
                },
                {
                    'source': "example",
                    'type': "bar",
                    'verified': "y",
                    'value': "ALL-CAPS",
                },
                {
                    'source': "example",
                    'type': "baz",
                    'verified': "n",
                    'value': "ignored",
                },
            ],
        })
    ) == [
        ("TEST-ID", "1"),
        ("FOO", "Example-Value"),
        ("BAR", "all-caps"),
    ]


#
# GregContactInfo tests
#


def test_get_contacts():
    get_contacts = mapper.GregContactInfo()
    assert list(
        get_contacts({
            'id': "1",
            'identities': [
                {
                    'type': 'private_mobile',
                    'source': "example",
                    'verified': 'automatic',
                    'value': '20123456',
                },
            ],
        })
    ) == [
        ("PRIVATEMOBILE", "20123456"),
    ]


#
# GregConsents tests
#


def test_get_consents():
    get_consents = mapper.GregConsents()
    assert get_consents({
        'id': "1",
        'consents': [
            {
                'type': "publish",
                'value': "yes",
            },
            {
                'type': "something",
                'value': "no",
            },
        ],
    }) == (
        "greg-publish",
    )


def test_get_consents_invalid():
    """ if we have an invalid consent value, we discard it. """
    get_consents = mapper.GregConsents()
    assert not get_consents({
        'id': "1",
        'consents': [
            {
                'type': "publish",
                'value': "garble",
            },
        ],
    })


def test_get_consents_duplicate():
    """ if we have a duplicate of a valid consent, we discard it. """
    get_consents = mapper.GregConsents()
    assert not get_consents({
        'id': "1",
        'consents': [
            {
                'type': "publish",
                'value': "yes",
            },
            {
                'type': "publish",
                'value': "no",
            },
        ],
    })


#
# GregRoles tests
#

class _ExampleRoles(mapper.GregRoles):
    type_map = {
        'emeritus': "TILKNYTTET/emeritus",
        'phd': ("ANSATT/vitenskapelig", "STUDENT/drgrad"),
    }


EXAMPLE_ORG_DATA = {
    'id': "3",
    'parent': "2",
    'active': True,
    'identifiers': [
        {
            'source': "orgreg",
            'name': "orgreg_id",
            'value': "3",
        },
    ],
}

EXAMPLE_ORG_IDS = (("GREG_OU_ID", "3"), ("ORGREG_OU_ID", "3"))


def test_get_roles():
    get_roles = _ExampleRoles()
    assert list(
        get_roles({
            'id': "1",
            'roles': [{
                'id': "32",
                'type': "phd",
                'start_date': datetime.date(2021, 11, 3),
                'end_date': datetime.date(2022, 2, 21),
                'orgunit': EXAMPLE_ORG_DATA,
            }],
        })
    ) == [
        (
            "ANSATT/vitenskapelig",
            EXAMPLE_ORG_IDS,
            datetime.date(2021, 11, 3),
            datetime.date(2022, 2, 21),
        ),
        (
            "STUDENT/drgrad",
            EXAMPLE_ORG_IDS,
            datetime.date(2021, 11, 3),
            datetime.date(2022, 2, 21),
        ),
    ]


def test_get_roles_unknown():
    get_roles = _ExampleRoles()
    assert list(
        get_roles({
            'id': "1",
            'roles': [{
                'id': "32",
                'type': "unknown",
                'start_date': datetime.date(1990, 1, 1),
                'end_date': datetime.date(1992, 12, 31),
                'orgunit': EXAMPLE_ORG_DATA,
            }],
        })
    ) == []


def test_get_roles_filter():
    get_roles = _ExampleRoles()
    assert list(
        get_roles(
            {
                'id': "1",
                'roles': [
                    {
                        'id': "32",
                        'type': "phd",
                        'start_date': datetime.date(1990, 1, 1),
                        'end_date': datetime.date(1992, 12, 31),
                        'orgunit': EXAMPLE_ORG_DATA,
                    },
                    {
                        'id': "33",
                        'type': "emeritus",
                        'start_date': datetime.date(1995, 1, 1),
                        'end_date': datetime.date(1996, 12, 31),
                        'orgunit': EXAMPLE_ORG_DATA,
                    },
                    {
                        'id': "34",
                        'type': "emeritus",
                        'start_date': datetime.date(1998, 1, 1),
                        'end_date': datetime.date(1999, 12, 31),
                        'orgunit': EXAMPLE_ORG_DATA,
                    },
                ],
            },
            filter_active_at=datetime.date(1995, 6, 1),
        )
    ) == [
        (
            "TILKNYTTET/emeritus",
            EXAMPLE_ORG_IDS,
            datetime.date(1995, 1, 1),
            datetime.date(1996, 12, 31),
        ),
    ]


#
# GregMapper.is_valid tests
#


class _ExampleMapper(mapper.GregMapper):
    get_affiliations = _ExampleRoles()


@pytest.fixture
def greg_mapper():
    return _ExampleMapper()


VALID_DATE = datetime.date(2020, 10, 15)
VALID_GUEST = {
    'id': "1",
    'registration_completed_date': datetime.date(2020, 10, 1),
    'date_of_birth': datetime.date(1990, 1, 1),
    'roles': [
        {
            'id': "32",
            'type': "phd",
            'start_date': datetime.date(2020, 10, 10),
            'end_date': datetime.date(2021, 12, 31),
            'orgunit': EXAMPLE_ORG_DATA,
        },
    ],
}


def test_mapper_is_active(greg_mapper):
    assert greg_mapper.is_active(VALID_GUEST, _today=VALID_DATE)


def test_mapper_is_active_empty(greg_mapper):
    """ a datasource missed result is not active. """
    assert not greg_mapper.is_active({'id': "1"})


@pytest.mark.parametrize(
    "regdate",
    [None, VALID_DATE + datetime.timedelta(days=7)],
    ids=["no-reg-date", "future-reg-date"],
)
def test_mapper_is_active_incomplete(greg_mapper, regdate):
    """ a greg person with pending results are not active. """
    invalid_guest = dict(VALID_GUEST)
    invalid_guest.update({
        'registration_completed_date': regdate,
    })
    assert not greg_mapper.is_active(invalid_guest, _today=VALID_DATE)


def test_mapper_is_active_no_dob(greg_mapper):
    """ a greg person without date of birth cannot be added to cerebrum. """
    invalid_guest = dict(VALID_GUEST)
    invalid_guest.update({
        'date_of_birth': None,
    })
    assert not greg_mapper.is_active(invalid_guest, _today=VALID_DATE)


def test_mapper_is_active_no_roles(greg_mapper):
    """ a greg person without date of birth cannot be added to cerebrum. """
    invalid_guest = dict(VALID_GUEST)
    invalid_guest.update({
        'roles': [],
    })
    assert not greg_mapper.is_active(invalid_guest, _today=VALID_DATE)
