# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.ou_import.ou_model` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime

import pytest
# import six

from Cerebrum.modules.ou_import import legacy_xml2ou
from Cerebrum.modules.xmlutils import xml2object


@pytest.fixture
def mapper():
    return legacy_xml2ou.LegacyObjectMapper()


@pytest.fixture
def empty_ou_data():
    """ An empty legacy ou object. """
    return xml2object.DataOU()


LOCATION_CODE = "012345"
LOCATION_TUPLE = (1, 23, 45)

PARENT_CODE = "012300"
PARENT_TUPLE = (1, 23, 0)


@pytest.fixture
def root_ou_data():
    """ A basic legacy ou object without parent. """
    xml_ou = xml2object.DataOU()
    xml_ou.add_id(xml2object.DataOU.NO_SKO, LOCATION_TUPLE)
    xml_ou.publishable = False
    xml_ou.start_date = None
    xml_ou.end_date = None
    return xml_ou


@pytest.fixture
def ou_data(root_ou_data):
    """ A basic legacy ou object with parent. """
    xml_ou = root_ou_data
    xml_ou.parent = (xml_ou.NO_SKO, PARENT_TUPLE)
    return xml_ou


# TODO:  xml_ou.add_usage_code("Tillatt Organisasjon")


#
# OrgUnitMapper tests
#


def test_get_id(mapper, ou_data):
    assert mapper.get_id(ou_data) == "sko:" + LOCATION_CODE


def test_get_parent_id(mapper, ou_data):
    assert mapper.get_parent_id(ou_data) == "sko:" + PARENT_CODE


def test_get_location_code(mapper, ou_data):
    assert mapper.get_location_code(ou_data) == LOCATION_CODE


DFO_ID = "12345678"
ORGREG_ID = "1234"


def test_get_external_ids(mapper, ou_data):
    ou_data.add_id(xml2object.DataOU.NO_DFO, DFO_ID)
    ou_data.add_id(xml2object.DataOU.NO_ORGREG, ORGREG_ID)
    items = dict(mapper.get_external_ids(ou_data))
    assert len(items) == 3
    assert all(key in items for key in ("NO_SKO", "DFO_OU_ID", "ORGREG_OU_ID"))
    assert items["NO_SKO"] == LOCATION_CODE
    assert items["DFO_OU_ID"] == DFO_ID
    assert items["ORGREG_OU_ID"] == ORGREG_ID


NAMES = [
    (xml2object.DataOU.NAME_ACRONYM, "en", "acr en"),
    (xml2object.DataOU.NAME_ACRONYM, "nb", "acr nb"),
    (xml2object.DataOU.NAME_SHORT, "en", "short en"),
    (xml2object.DataOU.NAME_SHORT, "nb", "short nb"),
    (xml2object.DataOU.NAME_LONG, "en", "long en"),
    (xml2object.DataOU.NAME_LONG, "nb", "long nb"),
    (xml2object.DataOU.NAME_LONG, "nn", "long nn"),
]


def test_get_names(mapper, ou_data):
    for name_type, name_lang, name_value in NAMES:
        ou_data.add_name(xml2object.DataName(name_type, name_value, name_lang))

    names = list(mapper.get_names(ou_data))

    assert len(names) == 10
    assert ("OU acronym", "en", "acr en") in names
    assert ("OU acronym", "nb", "acr nb") in names
    assert ("OU short", "en", "short en") in names
    assert ("OU short", "nb", "short nb") in names
    assert ("OU name", "en", "long en") in names
    assert ("OU name", "nb", "long nb") in names
    assert ("OU name", "nn", "long nn") in names
    assert ("OU display", "en", "long en") in names
    assert ("OU display", "nb", "long nb") in names
    assert ("OU display", "nn", "long nn") in names


CONTACTS = [
    (xml2object.DataContact.CONTACT_EMAIL, 1, "foo@example.org"),
    (xml2object.DataContact.CONTACT_FAX, 1, "+4701234567"),
    (xml2object.DataContact.CONTACT_PHONE, 1, "+4701234568"),
    (xml2object.DataContact.CONTACT_PHONE, 2, "+4701234569"),
    (xml2object.DataContact.CONTACT_URL, 1, "https://example.org/"),
]


def test_get_contact_info(mapper, ou_data):
    for ctype, priority, value in CONTACTS:
        ou_data.add_contact(xml2object.DataContact(ctype, value, priority))

    items = dict(mapper.get_contact_info(ou_data))

    assert len(items) == 4
    assert items["EMAIL"] == "foo@example.org"
    assert items["FAX"] == "+4701234567"
    assert items["PHONE"] == "+4701234568"
    assert items["URL"] == "https://example.org/"


ADDRS = [
    {
        'kind': xml2object.DataAddress.ADDRESS_BESOK,
        'street': ("", "Example Street 1", ""),
        'zip': "1234",
        'city': "Example Town",
        'country': "NO",
    },
    {
        'kind': xml2object.DataAddress.ADDRESS_POST,
        'street': ("c/o John Doe", "Example Street 1", "XYZ"),
        'zip': "1234",
        'city': "Example Town",
        'country': "",
    },
]


def test_get_addresses(mapper, ou_data):
    for addr_init in ADDRS:
        ou_data.add_address(xml2object.DataAddress(**addr_init))

    addrs = dict(mapper.get_addresses(ou_data))

    assert len(addrs) == 2
    assert addrs['STREET'] == {
        'address_text': "Example Street 1",
        'postal_number': "1234",
        'city': "Example Town",
        'country': None,
    }
    assert addrs['POST'] == {
        'address_text': "c/o John Doe\nExample Street 1\nXYZ",
        'postal_number': "1234",
        'city': "Example Town",
        'country': None,
    }


def test_is_valid_start_end(mapper, ou_data):
    """ start date in the past, and a future end date is valid. """
    ou_data.start_date = datetime.date.today() - datetime.timedelta(days=7)
    ou_data.end_date = datetime.date.today() + datetime.timedelta(days=7)
    assert mapper.is_valid(ou_data)


def test_is_valid_no_start_or_end(mapper, ou_data):
    """ missing start/end date is always valid. """
    assert mapper.is_valid(ou_data)


def test_is_valid_not_started(mapper, ou_data):
    """ start date in the future is not valid. """
    ou_data.start_date = datetime.date.today() + datetime.timedelta(days=7)
    assert not mapper.is_valid(ou_data)


def test_is_valid_ended(mapper, ou_data):
    """ end date in the past is not valid. """
    ou_data.end_date = datetime.date.today() - datetime.timedelta(days=7)
    assert not mapper.is_valid(ou_data)


def test_is_visible(mapper, ou_data):
    """ a valid ou is visible if *publishable* is set. """
    ou_data.publishable = True
    assert mapper.is_visible(ou_data)


def test_is_visible_hidden(mapper, ou_data):
    """ a valid ou is not visible if *publishable* is not set. """
    ou_data.publishable = False
    assert not mapper.is_visible(ou_data)


def test_is_visible_not_valid(mapper, ou_data):
    """ an invalid ou is not visible. """
    ou_data.publishable = True
    ou_data.start_date = datetime.date.today() + datetime.timedelta(days=7)
    assert not mapper.is_visible(ou_data)


def test_usage(mapper, ou_data):
    """ usage tags can be set. """
    ou_data.add_usage_code("Tillatt Organisasjon")
    assert set(mapper.get_usage(ou_data)) == set(("Tillatt Organisasjon",))


def test_usage_empty(mapper, ou_data):
    """ usage tags can be empty. """
    assert not set(mapper.get_usage(ou_data))


def test_usage_not_valid(mapper, ou_data):
    """ an invalid ou has no usage tags. """
    ou_data.start_date = datetime.date.today() + datetime.timedelta(days=7)
    ou_data.add_usage_code("Tillatt Organisasjon")
    assert set(mapper.get_usage(ou_data)) == set()
