# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.export.addresses`.

These tests are a bit messy, as we need to set up a lot of data fixtures.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.export import addresses as addr_export
from Cerebrum.export import base as base_export


#
# Some address types and source systems
#


ADDR_FOO = "a-foo-a04f36c3"
ADDR_BAR = "a-bar-a04f36c4"
ADDR_BAZ = "a-baz-a04f36c5"

SRC_FOO = "s-foo-a04f36c6"
SRC_BAR = "s-bar-a04f36c7"
SRC_BAZ = "s-baz-a04f36c8"

# A generic, non-existing code value (of any type)
INVALID = "missing-dea105ef"


@pytest.fixture
def addr_foo(constant_module, constant_creator):
    return constant_creator(constant_module._AddressCode, ADDR_FOO)


@pytest.fixture
def addr_bar(constant_module, constant_creator):
    return constant_creator(constant_module._AddressCode, ADDR_BAR)


@pytest.fixture
def addr_baz(constant_module, constant_creator):
    return constant_creator(constant_module._AddressCode, ADDR_BAZ)


@pytest.fixture
def src_foo(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_FOO)


@pytest.fixture
def src_bar(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAR)


@pytest.fixture
def src_baz(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode, SRC_BAZ)


@pytest.fixture
def addr_types(addr_foo, addr_bar, addr_baz):
    return (addr_foo, addr_bar, addr_baz)


@pytest.fixture
def source_systems(src_foo, src_bar, src_baz):
    return (src_foo, src_bar, src_baz)


# ... and some example data and helpers


CC_NO = ("no", "Norway", "+47")
CC_CH = ("ch", "Switzerland", "+41")


@pytest.fixture
def cc_no(constant_module, constant_creator):
    return constant_creator(constant_module._CountryCode, *CC_NO)


@pytest.fixture
def cc_ch(constant_module, constant_creator):
    return constant_creator(constant_module._CountryCode, *CC_CH)


ADDRS = [
    {
        # Frederikke
        'address_text': "Problemveien 11",
        'p_o_box': "1234",
        'postal_number': "0313",
        'city': "Oslo",
        'country': None,
    },
    {
        # Botanisk hage
        'address_text': "Trondheimsveien 23B",
        'p_o_box': None,
        'postal_number': "0562",
        'city': "Oslo",
        'country': None,
    },
    {
        # Domus Bibliotheca
        'address_text': "Karl Johans gt. 47",
        'p_o_box': None,
        'postal_number': "0162",
        'city': "Oslo",
        'country': CC_NO[0],
    },
    {
        # Cern
        'address_text': "Espl. des Particules 1",
        'p_o_box': None,
        'postal_number': "1217",
        'city': "Meyrin",
        'country': CC_CH[0],
    },
]


class _AddrHelper(object):
    """ Address setter/getter. """

    fields = ('address_text', 'p_o_box', 'postal_number', 'city', 'country')

    def __init__(self, countries, sources, addr_types):
        self.countries = countries
        self.sources = sources
        self.addr_types = addr_types

    def set(self, person, source_system, addr_type, addr_dict):
        source_system = self.sources[source_system]
        addr_type = self.addr_types[addr_type]
        values = {k: addr_dict.get(k) for k in self.fields}
        if values['country']:
            values['country'] = self.countries[values['country']]
        person.add_entity_address(source=source_system, type=addr_type,
                                  **values)

    def get(self, person, source_system, addr_type):
        for row in person.get_entity_address(source=source_system,
                                             type=addr_type):
            return {k: row[k] for k in self.fields}
        return None


@pytest.fixture
def addr_helper(cc_no, cc_ch, addr_types, source_systems):
    return _AddrHelper(
        {six.text_type(c): c for c in (cc_no, cc_ch)},
        {six.text_type(c): c for c in source_systems},
        {six.text_type(c): c for c in addr_types},
    )


@pytest.fixture
def person_a(person_creator, addr_helper):
    person, _ = next(person_creator(1))
    addr_helper.set(person, SRC_FOO, ADDR_FOO, ADDRS[0])
    addr_helper.set(person, SRC_BAR, ADDR_FOO, ADDRS[1])
    return person


@pytest.fixture
def person_b(person_creator, addr_helper):
    person, _ = next(person_creator(1))
    addr_helper.set(person, SRC_FOO, ADDR_FOO, ADDRS[2])
    addr_helper.set(person, SRC_BAR, ADDR_BAR, ADDRS[3])
    return person


@pytest.fixture
def person_c(person_creator, addr_helper):
    person, _ = next(person_creator(1))
    return person


#
# constant lookup helper tests
#


def test_get_address_types_str(const, addr_types):
    values = [six.text_type(c) for c in addr_types]
    results = addr_export.get_address_types(const, values)
    assert tuple(results) == addr_types


def test_get_address_types_verify(const, addr_types):
    results = addr_export.get_address_types(const, addr_types)
    assert tuple(results) == addr_types


def test_get_address_types_invalid(const, addr_foo):
    values = [ADDR_FOO, ADDR_BAR]  # ADDR_BAR doesn't exist yet
    with pytest.raises(LookupError) as exc_info:
        list(addr_export.get_address_types(const, values))
    error_msg = six.text_type(exc_info.value)
    assert ADDR_BAR in error_msg


def test_get_entity_types_verify(const):
    expected = [const.entity_person, const.entity_account]
    results = list(addr_export.get_entity_types(const, expected))
    assert results == expected


#
# address fetcher bad init tests
#

def test_init_fetcher_bad_addr_type(database):
    with pytest.raises(ValueError) as exc_info:
        addr_export._AddressFetcher(database, (INVALID,), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Invalid address type")
    assert INVALID in error_msg


def test_init_fetcher_empty_addr_types(database):
    with pytest.raises(ValueError) as exc_info:
        addr_export._AddressFetcher(database, (), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg == "No address types given"


def test_init_fetcher_duplicate_addr_type(database, addr_foo):
    with pytest.raises(ValueError) as exc_info:
        addr_export._AddressFetcher(database, (addr_foo, addr_foo), None, True)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("Duplicate address type")
    assert ADDR_FOO in error_msg


#
# address fetcher result tests
#


def test_fetch_filter(database, const, person_a, person_b, person_c,
                      addr_foo, src_bar):
    """ test fetching a narrow selection of data. """
    addr_types = (addr_foo,)
    sources = (src_bar,)
    entity_types = (const.entity_person,)
    fetcher = addr_export._AddressFetcher(database, addr_types,
                                          sources, entity_types)
    results = fetcher.get_all()

    # Only person_a has *one* address matching the criterias
    assert len(results) == 1
    assert person_a.entity_id in results
    assert len(results[person_a.entity_id]) == 1


@pytest.fixture
def addr_fetcher(database, const, person_a, person_b,
                 source_systems, addr_types):
    """ an address fetcher that fetches all our fixture types. """
    entity_types = None
    return addr_export._AddressFetcher(database, addr_types,
                                       source_systems, entity_types)


def test_fetch_all(addr_fetcher, person_a, person_b):
    results = addr_fetcher.get_all()
    assert len(results) == 2
    assert len(results[person_a.entity_id]) == 2
    assert len(results[person_b.entity_id]) == 2


def test_fetch_one_hit(addr_fetcher, person_a, person_b, addr_foo):
    results = addr_fetcher.get_one(person_a.entity_id)
    assert len(results) == 2
    assert all(r['address_type'] == addr_foo for r in results)


def test_fetch_one_miss(addr_fetcher, person_a, person_c, addr_foo):
    results = addr_fetcher.get_one(person_c.entity_id)
    assert results is base_export.MISSING


#
# address cache tests
#


@pytest.fixture
def addr_cache(database, const, source_systems, addr_types):
    entity_types = (const.entity_person,)
    return addr_export.AddressCache(database, addr_types,
                                    source_systems, entity_types)


def test_cache_get(addr_cache, person_a, person_b, person_c,
                   src_foo, src_bar, addr_foo):
    result = addr_cache.get(person_a.entity_id)
    assert len(result) == 2
    result_keys = set((a['source_system'], a['address_type']) for a in result)
    expect_keys = set([(src_foo, addr_foo), (src_bar, addr_foo)])
    assert result_keys == expect_keys


def test_cache_get_miss(addr_cache, person_a, person_b, person_c):
    result = addr_cache.get(person_c.entity_id)
    assert result is None


def test_cache_get_again(addr_cache, person_a, person_b, person_c):
    result = addr_cache.get(person_a.entity_id)
    assert len(result) == 2
    # test cached result for person-a is the same
    assert addr_cache.get(person_a.entity_id) == result


def test_cache_get_cached(addr_cache, person_a, person_b, person_c):
    addr_cache.update_all()

    result = addr_cache.get(person_a.entity_id)
    assert len(result) == 2

    result = addr_cache.get(person_c.entity_id)
    assert result is None


#
# address selector tests
#


@pytest.fixture
def addr_selector(addr_foo, source_systems):
    """ address selector for addr-type foo, system order (foo, bar, baz). """
    return addr_export.AddressSelector(addr_foo, source_systems)


def test_select_empty(addr_selector):
    assert addr_selector([]) is None


def test_select_miss(addr_selector, src_foo, addr_bar):
    addrs = [{
        'source_system': src_foo,
        'address_type': addr_bar,  # not the address type we're selecting
        'address': ADDRS[0],
    }]
    assert addr_selector(addrs) is None


def test_select_hit(addr_selector, src_foo, src_bar, addr_foo, addr_bar):
    addrs = [
        {
            'source_system': src_foo,  # has priority
            'address_type': addr_foo,
            'address': ADDRS[0],
        },
        {
            'source_system': src_foo,
            'address_type': addr_bar,  # wrong type
            'address': ADDRS[1],
        },
        {
            'source_system': src_bar,  # not prioritized
            'address_type': addr_foo,
            'address': ADDRS[2],
        },
    ]
    assert addr_selector(addrs) == ADDRS[0]
    assert addr_selector(reversed(addrs)) == ADDRS[0]


#
# address formatter tests
#

def test_format_base_address(cc_no):
    # address
    format_addr = addr_export._AddressFormatter()
    address = {
        # Cern
        'address_text': "  c/o Foo Bar  \n  Example Street 3  ",
        'p_o_box': " 123 ",
        'postal_number': " 1234 ",
        'city': " Example City",
        'country': cc_no,
    }
    result = format_addr(address)
    assert result == "\n".join((
        "123",
        "c/o Foo Bar",
        "Example Street 3",
        "1234 Example City",
        "Norway",
    ))


def test_format_base_address_minimal(cc_no):
    # address
    format_addr = addr_export._AddressFormatter()
    address = {
        # Cern
        'address_text': "Example Street 3",
        'p_o_box': None,
        'postal_number': "1234",
        'city': None,
        'country': None,
    }
    result = format_addr(address)
    assert result == "Example Street 3"


def test_format_ldap_postal_address(cc_no):
    # address
    address = {
        # Cern
        'address_text': "  c/o Foo Bar  \n  Example Street 3  ",
        'p_o_box': " 123 ",
        'postal_number': " 1234 ",
        'city': " Example City",
        'country': cc_no,
    }
    result = addr_export.format_ldap_postal_address(address)
    assert result == "$".join((
        "Pb. 123",
        "c/o Foo Bar",
        "Example Street 3",
        "1234 Example City",
        "Norway",
    ))


def test_format_ldap_street_address(cc_no):
    # address
    address = {
        # Cern
        'address_text': "  c/o Foo Bar  \n  Example Street 3  ",
        'p_o_box': " 123 ",
        'postal_number': " 1234 ",
        'city': " Example City",
        'country': cc_no,
    }
    result = addr_export.format_ldap_street_address(address)
    assert result == ", ".join((
        "c/o Foo Bar",
        "Example Street 3",
        "1234 Example City",
        "Norway",
    ))
