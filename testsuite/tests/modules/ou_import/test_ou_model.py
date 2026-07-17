# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.ou_import.ou_model` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.ou_import import ou_model


#
# test location code normalizers
#


VALID_LOCATION_CODES = [
    # un-nomalized, normalized, tuple
    (112233, "112233", (11, 22, 33)),
    (123, "000123", (0, 1, 23)),
    (" 54321 ", "054321", (5, 43, 21)),
]


@pytest.mark.parametrize(
    "value, expected",
    [(t[0], t[1]) for t in VALID_LOCATION_CODES],
    ids=[t[1] for t in VALID_LOCATION_CODES],
)
def test_normalize_sko(value, expected):
    assert ou_model.normalize_sko(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "abcdef",  # non-digit
        1234567,   # too many digits
    ],
)
def test_normalize_sko_error(value):
    with pytest.raises(ValueError) as exc_info:
        ou_model.normalize_sko(value)

    error = six.text_type(exc_info.value)
    assert error.startswith("location code must be")


@pytest.mark.parametrize(
    "value, expected",
    [(t[0], t[2]) for t in VALID_LOCATION_CODES],
    ids=[t[1] for t in VALID_LOCATION_CODES],
)
def test_sko_to_tuple(value, expected):
    assert ou_model.sko_to_tuple(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [(t[2], t[1]) for t in VALID_LOCATION_CODES],
    ids=[t[1] for t in VALID_LOCATION_CODES],
)
def test_tuple_to_sko(value, expected):
    assert ou_model.tuple_to_sko(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        (123, 3, 21),  # three-digit field value
        (1, 2, 3, 4),  # more than three fields
        (1, 2),        # less than three fields
    ],
)
def test_tuple_to_sko_error(value):
    with pytest.raises(ValueError) as exc_info:
        ou_model.tuple_to_sko(value)

    error = six.text_type(exc_info.value)
    assert error.startswith("location tuple")


#
# PreparedOrgUnit tests
#


EXAMPLE_LOCATION_CODE = "112233"
EXAMPLE_LOCATION_TUPLE = (11, 22, 33)


@pytest.fixture
def ou():
    return ou_model.PreparedOrgUnit(EXAMPLE_LOCATION_CODE, is_valid=True)


def test_ou_init(ou):
    assert ou.location_code == EXAMPLE_LOCATION_CODE
    assert ou.is_valid
    assert not ou.is_visible


def test_ou_init_location_tuple(ou):
    return ou_model.PreparedOrgUnit(EXAMPLE_LOCATION_TUPLE)
    assert ou.location_code == EXAMPLE_LOCATION_CODE


def test_ou_repr(ou):
    repr_text = repr(ou)
    assert "PreparedOrgUnit" in repr_text
    assert "location_code=" in repr_text
    assert "is_valid=True" in repr_text


def test_ou_location_t(ou):
    assert ou.location_code == EXAMPLE_LOCATION_CODE
    assert ou.location_t == EXAMPLE_LOCATION_TUPLE


def test_ou_address(ou):
    assert ou.addresses == tuple()
    ou.add_address("example", {'address_text': "Example Street 1",
                               'p_o_box': "1234"})
    assert len(ou.addresses) == 1
    assert ou.addresses[0][0] == "example"


def test_ou_contact_info(ou):
    assert ou.contact_info == tuple()
    ou.add_contact_info("example", "foo")
    assert ou.contact_info == (("example", "foo"),)


def test_ou_external_ids(ou):
    assert ou.external_ids == tuple()
    ou.add_external_id("example", "foo")
    assert ou.external_ids == (("example", "foo"),)


def test_ou_names(ou):
    assert ou.names == tuple()
    ou.add_name("example", "en", "foo")
    assert ou.names == (("example", "en", "foo"),)


def test_ou_to_dict(ou):
    ou.add_address("POST", {'address_text': "Example Street 1",
                            'p_o_box': "1234"})
    ou.add_external_id("NO_SKO", EXAMPLE_LOCATION_CODE)
    ou.add_contact_info("EMAIL", "foo@example.org")
    ou.add_name("OU name", "en", "Example unit")
    ou.add_usage_code("foo")

    data = ou.to_dict()
    assert data == {
        'location': EXAMPLE_LOCATION_CODE,
        'is_valid': True,
        'is_visible': False,
        'addresses': {
            'POST': {
                'address_text': "Example Street 1",
                'p_o_box': "1234",
                'postal_number': None,
                'city': None,
                'country': None,
            },
        },
        'contact_info': {
            'EMAIL': "foo@example.org",
        },
        'external_ids': {
            'NO_SKO': EXAMPLE_LOCATION_CODE,
        },
        'names': {
            'OU name': {
                'en': "Example unit",
            },
        },
        'usage_codes': ("foo",),
    }


def test_ou_from_dict():
    ou = ou_model.PreparedOrgUnit.from_dict({
        'location': EXAMPLE_LOCATION_CODE,
        'is_valid': True,
        'is_visible': False,
        'addresses': {
            "POST": {
                "address_text": "Example Street 1",
                "p_o_box": "1234",
            },
        },
        'contact_info': {
            "EMAIL": "foo@example.org",
        },
        'external_ids': {
            "NO_SKO": EXAMPLE_LOCATION_CODE,
        },
        'names': {
            "OU name": {
                "no": "Eksempelenhet",
                "en": "Example unit",
            },
        },
        'usage_codes': ["foo", "bar"],
    })

    assert ou.location_code == EXAMPLE_LOCATION_CODE
    assert ou.is_valid
    assert not ou.is_visible
    assert "POST" in dict(ou.addresses)
    assert "EMAIL" in dict(ou.contact_info)
    assert "NO_SKO" in dict(ou.external_ids)
    assert "OU name" in [n[0] for n in ou.names]
    assert ou.usage_codes == set(("foo", "bar"))


#
# OrgUnitMapper tests
#


@pytest.fixture
def mapper():
    return ou_model.OrgUnitMapper()


def test_mapper_init(mapper):
    assert mapper


def test_mapper_repr(mapper):
    repr_text = repr(mapper)
    assert "OrgUnitMapper" in repr_text


def test_mapper_get_id_abstract(mapper):
    with pytest.raises(NotImplementedError):
        mapper.get_id({})


def test_mapper_get_parent_id_abstract(mapper):
    with pytest.raises(NotImplementedError):
        mapper.get_parent_id({})


def test_mapper_get_location_code(mapper):
    assert mapper.get_location_code({}) is None


def test_mapper_get_external_ids(mapper):
    assert list(mapper.get_external_ids({})) == []


def test_mapper_get_names(mapper):
    assert list(mapper.get_names({})) == []


def test_mapper_get_contact_info(mapper):
    assert list(mapper.get_contact_info({})) == []


def test_mapper_get_addresses(mapper):
    assert list(mapper.get_addresses({})) == []


def test_mapper_is_valid(mapper):
    assert not mapper.is_valid({})


def test_mapper_is_visible(mapper):
    assert not mapper.is_visible({})


def test_mapper_get_usage(mapper):
    assert list(mapper.get_usage({})) == []


class _ExampleMapper(ou_model.OrgUnitMapper):

    def get_id(self, ou_data):
        return "internal-id:2"

    def get_parent_id(self, ou_data):
        return "internal-id:1"

    def get_location_code(self, ou_data):
        return EXAMPLE_LOCATION_CODE

    def is_valid(self, ou_data):
        return True


def test_mapper_prepare():
    mapper = _ExampleMapper()
    prepared = mapper.prepare({})
    assert prepared.location_code == EXAMPLE_LOCATION_CODE
    assert prepared.is_valid
    assert not prepared.is_visible
