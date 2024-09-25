# encoding: utf-8
"""
Tests for :class:`Cerebrum.modules.import_utils.syncs.AddressSync`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.import_utils import syncs


# Constant values

SOURCE_SYSTEM = "sys-1f073188eaba"
CC_NO = ("no", "Norway", "+47")
CC_CH = ("ch", "Switzerland", "+41")

# Example addresses

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

    def __init__(self, source_system, countries):
        self.source = source_system
        self.countries = countries

    def set(self, person, addr_type, addr_dict):
        values = {k: addr_dict.get(k) for k in self.fields}
        if values['country']:
            values['country'] = self.countries[values['country']]
        person.add_entity_address(source=self.source, type=addr_type, **values)

    def get(self, person, addr_type):
        for row in person.get_entity_address(source=self.source,
                                             type=addr_type):
            return {k: row[k] for k in self.fields}
        return None


@pytest.fixture
def source_system(constant_module, constant_creator):
    return constant_creator(constant_module._AuthoritativeSystemCode,
                            SOURCE_SYSTEM)


@pytest.fixture
def cc_no(constant_module, constant_creator):
    return constant_creator(constant_module._CountryCode, *CC_NO)


@pytest.fixture
def cc_ch(constant_module, constant_creator):
    return constant_creator(constant_module._CountryCode, *CC_CH)


@pytest.fixture
def addr_helper(source_system, cc_no, cc_ch):
    return _AddrHelper(source_system, {CC_NO[0]: cc_no, CC_CH[0]: cc_ch})


@pytest.fixture
def person(person_creator):
    person, _ = next(person_creator(1))
    return person


@pytest.fixture
def sync(database, source_system):
    return syncs.AddressSync(database, source_system)


#
# Tests
#


def test_sync_init(sync, source_system):
    assert sync.source_system == source_system


def test_name_sync_get_type(sync, const):
    """ check that sync can look up address types. """
    addr_type = const.address_post
    addr_strval = six.text_type(addr_type)
    addr_intval = int(addr_type)
    assert sync.get_type(addr_strval) is addr_type
    assert sync.get_type(addr_intval) is addr_type


def test_sync_add_remove(sync, const, addr_helper, person):
    """ check that sync can add and remove values. """
    addr_helper.set(person, const.address_post, ADDRS[0])

    new = [(const.address_street, ADDRS[1])]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set((const.address_street,))
    assert updated == set()
    assert removed == set((const.address_post,))

    # Check that our addresses are set as expected
    assert addr_helper.get(person, const.address_street)
    assert not addr_helper.get(person, const.address_post)


def test_sync_update(sync, const, addr_helper, person):
    """ check that sync can update existing values. """
    addr_helper.set(person, const.address_post, ADDRS[0])

    new = [(const.address_post, ADDRS[1])]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set((const.address_post,))
    assert removed == set()

    # Check that our addresses are set as expected
    addr = addr_helper.get(person, const.address_post)
    assert addr['address_text'] == ADDRS[1]['address_text']


def test_sync_no_change(sync, const, addr_helper, person):
    """ check that sync does nothing if given existing values. """
    addr_helper.set(person, const.address_post, ADDRS[0])

    new = [(const.address_post, ADDRS[0])]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set()
    assert removed == set()
    assert addr_helper.get(person, const.address_post)


def test_sync_affected(database, const, addr_helper, person):
    """ check that affect_types only touches the given types. """
    addr_helper.set(person, const.address_post, ADDRS[0])
    addr_helper.set(person, const.address_street, ADDRS[1])

    sync = syncs.AddressSync(database, addr_helper.source,
                             affect_types=(const.address_post,))
    # no addresses - remove all affected types
    added, updated, removed = sync(person, [])

    assert not added
    assert not updated
    assert removed == set((const.address_post,))

    # Check that our contact values are set as expected
    assert addr_helper.get(person, const.address_street)
    assert not addr_helper.get(person, const.address_post)


def test_sync_country(sync, const, addr_helper, cc_ch, person):
    """ check that sync can handle country codes. """
    addr_helper.set(person, const.address_post, ADDRS[2])

    new = [(const.address_post, ADDRS[3])]
    added, updated, removed = sync(person, new)

    # Check add/update/remove return value
    assert added == set()
    assert updated == set((const.address_post,))
    assert removed == set()

    # Check that our addresses are set as expected
    addr = addr_helper.get(person, const.address_post)
    assert addr['country'] == int(cc_ch)


def test_sync_duplicate(sync, const, person):
    """ check that it is an error to set two different values. """
    new = [
        (const.address_post, ADDRS[0]),
        (const.address_post, ADDRS[1]),
    ]
    with pytest.raises(ValueError) as exc_info:
        sync(person, new)
    error_msg = six.text_type(exc_info.value)
    assert error_msg.startswith("duplicate ")
