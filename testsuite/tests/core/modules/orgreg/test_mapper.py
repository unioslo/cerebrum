# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.orgreg.mapper` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
import six

from Cerebrum.modules.orgreg import mapper


@pytest.fixture
def mapper_obj():
    return mapper.OrgregMapper()


#
# test get_external_key
#


VALID_EXTERNAL_KEYS = {
    'ouId': "1",
    # external ids
    'externalKeys': [
        {'sourceSystem': "foo", 'type': "id", 'value': "123"},
        {'sourceSystem': "sapuio", 'type': "legacy_stedkode",
         'value': "102030"},
        {'sourceSystem': "dfo_sap", 'type': "dfo_org_id", 'value': "01234567"},
    ],
}


DUPLICATE_EXTERNAL_KEYS = {
    'ouId': "1",
    'externalKeys': [
        {'sourceSystem': "bar", 'type': "id", 'value': "123"},
        {'sourceSystem': "bar", 'type': "id", 'value': "234"},  # duplicate
    ],
}

NO_EXTERNAL_KEYS = {
    'ouId': "1",
    'externalKeys': [],
}


def test_get_external_key():
    """ get any existing external key """
    assert mapper.get_external_key(VALID_EXTERNAL_KEYS, "foo", "id") == "123"


def test_get_external_key_duplicate():
    """ duplicate keys should cause an error. """
    with pytest.raises(ValueError) as exc_info:
        mapper.get_external_key(DUPLICATE_EXTERNAL_KEYS, "bar", "id")
    error = six.text_type(exc_info.value)
    assert error.startswith("duplicate external key")


def test_get_external_key_missing():
    """ missing keys should cause an error. """
    with pytest.raises(ValueError) as exc_info:
        mapper.get_external_key(NO_EXTERNAL_KEYS, "foo", "no-id")
    error = six.text_type(exc_info.value)
    assert error.startswith("no external key")


def test_get_location_code(mapper_obj):
    """ location code should get sapuio/legacy_stedkode """
    assert mapper_obj.get_location_code(VALID_EXTERNAL_KEYS) == "102030"


def test_get_location_code_missing(mapper_obj):
    """ missing location code should return None """
    assert mapper_obj.get_location_code(NO_EXTERNAL_KEYS) is None


def test_get_external_ids(mapper_obj):
    """ get_external_ids should get orgreg-id, dfo-id, location code """
    ext_ids = dict(mapper_obj.get_external_ids(VALID_EXTERNAL_KEYS))
    assert ext_ids == {
        "ORGREG_OU_ID": "1",
        "DFO_OU_ID": "01234567",
        "NO_SKO": "102030",
    }


def test_get_external_ids_partial(mapper_obj):
    """ missing dfo-id should cause an error. """
    with pytest.raises(ValueError) as exc_info:
        dict(mapper_obj.get_external_ids(NO_EXTERNAL_KEYS))
    error = six.text_type(exc_info.value)
    assert error.startswith("no external key")


#
# test OrgregMapper ids
#


VALID_PARENT_ID = {
    'ouId': "2",
    'parent': "1",
}


def test_get_id(mapper_obj):
    """ get_id should get an internal identifier """
    assert mapper_obj.get_id(VALID_PARENT_ID) == "orgreg-id:2"


def test_get_parent(mapper_obj):
    """ get_parent should get an internal identifier, if it exists"""
    assert mapper_obj.get_parent_id(VALID_PARENT_ID) == "orgreg-id:1"


def test_get_parent_missing(mapper_obj):
    """ get_parent should return None if no parent is set. """
    assert mapper_obj.get_parent_id({'ouId': "1"}) is None


#
# test OrgregMapper.get_addresses
#


VALID_ADDRESSES = {
    'ouId': "1",
    'postalAddress': {
        'street': "Example Street 1",
        'extended': "c/o Ola Nordmann",
        'country': "NO",
        'postalCode': "0123",
        'city': "Example Town",
    },
    'visitAddress': {
        'street': "Example Street 1",
        'country': "NO",
        'postalCode': "0123",
        'city': "Example Town",
    },
}


def test_get_address_post(mapper_obj):
    addrs = dict(mapper_obj.get_addresses(VALID_ADDRESSES))
    addr = addrs["POST"]
    assert addr == {
        'address_text': "Example Street 1\nc/o Ola Nordmann",
        'p_o_box': None,
        'postal_number': "0123",
        'city': "Example Town",
        'country': None,
    }


def test_get_address_street(mapper_obj):
    addrs = dict(mapper_obj.get_addresses(VALID_ADDRESSES))
    addr = addrs["STREET"]
    assert addr == {
        'address_text': "Example Street 1",
        'p_o_box': None,
        'postal_number': "0123",
        'city': "Example Town",
        'country': None,
    }


def test_get_address_missing(mapper_obj):
    """ addresses are not required. """
    addrs = dict(mapper_obj.get_addresses({'ouId': "1"}))
    assert not addrs


def test_get_address_partial(mapper_obj):
    """ 'steet' or 'extended' is required for a valid address. """
    addrs = dict(
        mapper_obj.get_addresses({
            'ouId': "1",
            'postalAddress': {
                'country': "SE",
                'postalCode': "0123",
                'city': "Example Town",
            },
        })
    )
    assert not addrs


def test_get_address_minimal(mapper_obj):
    """ only 'steet' or 'extended' is required for a valid address. """
    addrs = dict(
        mapper_obj.get_addresses({
            'ouId': "1",
            'postalAddress': {
                'street': "Example Street 1",
            },
        })
    )
    addr = addrs["POST"]
    assert addr == {
        'address_text': "Example Street 1",
        'p_o_box': None,
        'postal_number': None,
        'city': None,
        'country': None,
    }


#
# test OrgregMapper.get_contact_info
#


VALID_CONTACT_INFO = {
    'ouId': "1",
    'email': "foo@example.org",
    'fax': "+4722000001",
    'phone': "+4722000000",
    'homepage': {
        'nb': "https://nb.example.org/",
        'en': "https://en.example.org/",
        'se': "https://se.example.org/",
    },
}


def test_get_contact_info(mapper_obj):
    cinfo = dict(mapper_obj.get_contact_info(VALID_CONTACT_INFO))
    assert cinfo == {
        'EMAIL': "foo@example.org",
        'FAX': "+4722000001",
        'PHONE': "+4722000000",
        'URL': "https://nb.example.org/",
    }


def test_get_contact_info_url_fallback(mapper_obj):
    cinfo = dict(
        mapper_obj.get_contact_info({
            'ouId': "1",
            'homepage': {
                'en': "https://en.example.org/",
                'se': "https://se.example.org/",
            },
        })
    )
    assert cinfo == {
        'URL': "https://en.example.org/",
    }


#
# test OrgregMapper.get_names
#


def _generate_names(**kwargs):
    names = {
        'ouId': "1",  # required
        'shortName': {'nb': 'nb-short-default'},  # required
        'acronym': None,
        'name': None,
        'longName': None,
    }
    names.update(kwargs)
    return names


NAME_FULL = _generate_names(
    shortName={'nb': "nb-short", 'en': "en-short"},
    acronym={'nb': "nb-acro", 'en': "en-acro"},
    name={'nb': "nb-name", 'en': "en-name"},
    longName={'nb': "nb-long", 'en': "en-long"},
)


def test_get_names(mapper_obj):
    names = list(mapper_obj.get_names(NAME_FULL))
    assert len(names) == 8


def test_get_name_short(mapper_obj):
    names = list(mapper_obj.get_names(NAME_FULL))
    assert ("OU short", "nb", "nb-short") in names
    # Note: we use 'nb' as 'en' for short name!
    assert ("OU short", "en", "nb-short") in names


def test_get_name_acronym(mapper_obj):
    names = list(mapper_obj.get_names(NAME_FULL))
    assert ("OU acronym", "nb", "nb-acro") in names
    assert ("OU acronym", "en", "en-acro") in names


def test_get_name_name(mapper_obj):
    names = list(mapper_obj.get_names(NAME_FULL))
    assert ("OU name", "nb", "nb-name") in names
    assert ("OU name", "en", "en-name") in names


def test_get_name_display(mapper_obj):
    names = list(mapper_obj.get_names(NAME_FULL))
    # Note: defaults to 'name'
    assert ("OU display", "nb", "nb-name") in names
    assert ("OU display", "en", "en-name") in names


def test_get_name_display_fallback(mapper_obj):
    ou_data = _generate_names(
        shortName={'nb': "nb-short", 'en': "en-short"},
        longName={'nb': "nb-long", 'en': "en-long"},
    )
    names = list(mapper_obj.get_names(ou_data))
    # Note: defaults to 'name'
    assert ("OU display", "nb", "nb-long") in names
    assert ("OU display", "en", "en-long") in names


def test_get_name_nb_only(mapper_obj):
    ou_data = _generate_names(
        shortName={'nb': "nb-short"},
        acronym={'nb': "nb-acro"},
        name={'nb': "nb-name"},
        longName={'nb': "nb-long"},
    )
    names = list(mapper_obj.get_names(ou_data))
    # note: the four names in nb, and short in en
    assert len(names) == 5


def test_get_name_minimal(mapper_obj):
    ou_data = _generate_names()
    names = list(mapper_obj.get_names(ou_data))
    assert len(names) == 2
    assert set(name_type for name_type, _, _ in names) == set(("OU short",))


def test_get_name_omit_empty(mapper_obj):
    ou_data = _generate_names(acronym={'en': ""})
    names = list(mapper_obj.get_names(ou_data))
    assert len(names) == 2


def test_get_name_missing_short(mapper_obj):
    ou_data = _generate_names(shortName={'nb': ""})
    with pytest.raises(ValueError) as exc_info:
        list(mapper_obj.get_names(ou_data))
    error = six.text_type(exc_info.value)
    assert error.startswith("missing shortName")


#
# test OrgregMapper.is_valid
#


DATE_PAST = datetime.date(1996, 6, 27)
DATE_TODAY = datetime.date(1996, 6, 28)
DATE_FUTURE = datetime.date(1996, 6, 29)


def _generate_valid(**kwargs):
    ou_data = {"ouId": "1"}
    ou_data.update(kwargs)
    # start date with some clearance from datetime.date.today()
    ou_data.setdefault(
        "validFrom",
        datetime.date.today() - datetime.timedelta(days=7),
    )
    return ou_data


def test_is_valid(mapper_obj):
    ou_data = _generate_valid(validFrom=DATE_PAST, validTo=DATE_FUTURE)
    assert mapper_obj.is_valid(ou_data, _today=DATE_TODAY)


def test_is_valid_no_end(mapper_obj):
    ou_data = _generate_valid(validFrom=DATE_PAST)
    assert mapper_obj.is_valid(ou_data, _today=DATE_TODAY)


def test_is_valid_not_started(mapper_obj):
    ou_data = _generate_valid(validFrom=DATE_FUTURE)
    assert not mapper_obj.is_valid(ou_data, _today=DATE_TODAY)


def test_is_valid_ended(mapper_obj):
    ou_data = _generate_valid(validFrom=DATE_PAST, validTo=DATE_PAST)
    assert not mapper_obj.is_valid(ou_data, _today=DATE_TODAY)


def test_is_valid_today(mapper_obj):
    assert mapper_obj.is_valid(_generate_valid())


#
# test OrgregMapper.is_visible
#


def test_is_visible(mapper_obj):
    ou_data = _generate_valid(tags=["elektronisk_katalog"])
    assert mapper_obj.is_visible(ou_data)


def test_is_visible_missing_tag(mapper_obj):
    ou_data = _generate_valid()
    assert not mapper_obj.is_visible(ou_data)


def test_is_visible_expired(mapper_obj):
    ou_data = _generate_valid(
        tags=["elektronisk_katalog"],
        validTo=(datetime.date.today() - datetime.timedelta(days=3)),
    )
    assert not mapper_obj.is_visible(ou_data)


#
# test OrgregMapper.get_usage
#


def test_get_usage(mapper_obj):
    ou_data = _generate_valid(tags=["arkivsted", "tillatt_organisasjon"])
    assert mapper_obj.get_usage(ou_data) == (
        "Arkivsted",
        "Tillatt Organisasjon",
    )


def test_get_usage_partial(mapper_obj):
    ou_data = _generate_valid(tags=["arkivsted", "elektronisk_katalog"])
    assert mapper_obj.get_usage(ou_data) == (
        "Arkivsted",
    )


def test_get_usage_empty(mapper_obj):
    ou_data = _generate_valid(tags=[])
    assert mapper_obj.get_usage(ou_data) == tuple()


def test_get_usage_expired(mapper_obj):
    ou_data = _generate_valid(
        tags=["arkivsted", "tillatt_organisasjon"],
        validTo=(datetime.date.today() - datetime.timedelta(days=3)),
    )
    assert mapper_obj.get_usage(ou_data) == tuple()
