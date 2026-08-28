# -*- coding: utf-8 -*-
#
# Copyright 2025-2026 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Fetch, cache, and process addresses.

This module provides helpers for fetching, caching, selecting and filtering
addresses by source and type.

The caching functionality is useful in any scenario where we look up addresses
in a single read-only transaction.  The selection functionality is useful for
selecting a single address value in any scenario.


Address format
---------------
The :class:`AddressCache` cache returns normalized address :class:`dict`
objects, with an address and some address metadata:
::

    {
        'entity_id': int,
        'source_system': _AuthoritativeSystemCode,
        'address_type': _AddressCode,
        'address': {
            'address_text': str,
            'p_o_box': str,
            'postal_number': str,
            'city': str,
            'country': _CountryCode,
        },
    }

The other helper classes work on these objects.  Note that any of the address
fields may be ``None``.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import re

from Cerebrum import Constants
from Cerebrum.Entity import EntityAddress
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import hex_escape_match
from Cerebrum.utils.aggregate import dict_collect_lists
from Cerebrum.utils.descriptors import lazy_property
from Cerebrum.utils.sorting import make_priority_lookup
from . import base


logger = logging.getLogger(__name__)


def get_source_system_types(co, values):
    """ Look up a sequence of _AuthoritativeSystemCode values. """
    for value in values:
        yield co.get_constant(Constants._AuthoritativeSystemCode, value)


def get_address_types(co, values):
    """ Look up a sequence of _AddressCode values. """
    for value in values:
        yield co.get_constant(Constants._AddressCode, value)


def get_entity_types(co, values):
    """ Look up a sequence of _EntityTypeCode values. """
    for value in values:
        yield co.get_constant(Constants._EntityTypeCode, value)


def _check_constants(codes, code_type, code_hint,
                     unique=True, allow_empty=False):
    """ Check a sequence of _CerebrumCode values of a specific type. """
    codes = tuple(codes)
    if not (allow_empty or codes):
        raise ValueError("No %s types given" % (code_hint,))
    for code in codes:
        if not isinstance(code, code_type):
            raise ValueError("Invalid %s type: %s" % (code_hint, repr(code)))
    if unique and len(codes) != len(set(codes)):
        raise ValueError("Duplicate %s type given: %s"
                         % (code_hint, repr(codes)))
    return codes


class _AddressFetcher(base.EntityFetcher):
    """ Fetch address data. """

    def __init__(self, db, address_types, source_systems, entity_types):
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.address_types = (
            None if address_types is None
            else _check_constants(address_types, Constants._AddressCode,
                                  "address")
        )
        self.source_systems = (
            None if source_systems is None
            else _check_constants(source_systems,
                                  Constants._AuthoritativeSystemCode,
                                  "source system")
        )
        self.entity_types = (
            None if entity_types is None
            else _check_constants(entity_types, Constants._EntityTypeCode,
                                  "entity")
        )

    @lazy_property
    def address_type_map(self):
        const_type = Constants._AddressCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def source_system_map(self):
        const_type = Constants._AuthoritativeSystemCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    def _normalize_row(self, row):
        return {
            'entity_id': row['entity_id'],
            'source_system': self.source_system_map[row['source_system']],
            'address_type': self.address_type_map[row['address_type']],
            'address': {
                'address_text': row['address_text'],
                'p_o_box': row['p_o_box'],
                'postal_number': row['postal_number'],
                'city': row['city'],
                'country': (
                    None if row['country'] is None
                    else self._const.Country(row['country'])
                ),
            },
        }

    def _get_results(self, entity_id=None):
        addr_db = EntityAddress(self._db)
        for row in addr_db.list_entity_addresses(
                entity_type=self.entity_types,
                source_system=self.source_systems,
                address_type=self.address_types,
                entity_id=entity_id):
            data = self._normalize_row(row)
            yield (data['entity_id'], data)

    def get_one(self, entity_id):
        """ Fetch addresses for one entity. """
        entity_data = [
            addr_data
            for _, addr_data in self._get_results(entity_id=int(entity_id))
        ]
        return entity_data or base.MISSING

    def get_all(self):
        """ Fetch address data for all entities. """
        return dict_collect_lists(self._get_results())


class AddressCache(base.EntityCache):
    """
    Address data cache.

    The cache can optionally limit results to specific address types,
    source systems, and/or entity types.
    """
    def __init__(self, db, address_types=None, source_systems=None,
                 entity_types=None):
        """
        :type db: Cerebrum.database.Database
        :type address_types: collection of _AddressCode, or None
        :type source_systems: collection of _AuthoritativeSystemCode, or None
        :type entity_types: collection of _EntityTypeCode, or None
        """
        fetcher = _AddressFetcher(db, address_types, source_systems,
                                  entity_types)
        super(AddressCache, self).__init__(fetcher)


class AddressSelector(object):
    """
    Helper to select a single address from an address cache result.

    Use this to get the best matching address of a given type for a given
    entity.  Example use:
    ::

        # Select POST address, using the default system lookup order
        select = AddressSelector(const.address_post,
                                 const.get_system_lookup_order())
        cache = AddressCache(db)

        match = select(cache.get(entity_id, []))
        if match:
            print(match['address_text'], match['postal_number'], match['city'])

    """

    def __init__(self, address_type, system_priority):
        """
        Filter and select the best matching address of a given type.

        :param address_type: A single address type to select
        :param system_priority: An ordered list of sources to select from
        """
        self.address_type = _check_constants(
            (address_type,), Constants._AddressCode, "address")[0]
        self.system_priority = _check_constants(
            system_priority, Constants._AuthoritativeSystemCode,
            "source system")
        self._system_key = make_priority_lookup(
            [int(s) for s in system_priority]
        )

    def _sort_key(self, addr_data):
        return self._system_key(int(addr_data['source_system']))

    def __call__(self, address_list):
        """
        Find preferred address from a list of results.

        :param address_list: An iterable of address objects

        :rtype: dict
        :returns: A matching address, or ``None``
        """
        matching_types = [
            addr_data
            for addr_data in address_list
            if addr_data['address_type'] == self.address_type
            and addr_data['source_system'] in self.system_priority
        ]
        for addr_data in sorted(matching_types, key=self._sort_key):
            return addr_data['address']
        return None


#
# Address formatters
#


def _normalize(value):
    return (value or "").strip() or None


class _AddressFormatter(object):
    """
    Format a dict of address parts into an address string.

    Default/base implementation, formats a multiline string:
    ::

        p_o_box
        address_text...
        postal_number city
        country

    """
    separator = "\n"

    def _get_country(self, fields):
        """ Get country value. """
        code = fields['country']
        if code:
            return code.country
        return None

    def _get_city_line(self, fields):
        """
        Format a city line.

        :returns:
            A post code/city line.

            One of: "<post-code> <city>" or "<post-code>" or "<city>" or None
        """
        city = _normalize(fields['city'])
        postcode = _normalize(fields['postal_number'])
        country = self._get_country(fields)
        if city or (postcode and country):
            return " ".join(v for v in (postcode, city) if v)
        return None

    def _get_values(self, fields):
        """ Get iterator over individual address parts. """
        yield _normalize(fields['p_o_box'])
        for addr_line in (fields['address_text'] or "").split("\n"):
            yield _normalize(addr_line) or None
        yield self._get_city_line(fields)
        yield self._get_country(fields)

    def _escape(self, value):
        """ Escape individual address parts before final formatting. """
        return value

    def __call__(self, fields):
        return self.separator.join(
            self._escape(value)
            for value in self._get_values(fields)
            if value
        ) or None


class _LdapPostalAddress(_AddressFormatter):
    """ Format a postalAddress field for LDAP.  """
    separator = "$"
    postal_escape_re = re.compile(r'[$\\]')

    def _escape(self, value):
        return self.postal_escape_re.sub(hex_escape_match, value)

    def _get_values(self, fields):
        # "Pb. <po-box>"
        postbox = _normalize(fields['p_o_box'])
        yield ("Pb. {}".format(postbox) if postbox else None)

        # address lines
        for addr_line in (fields['address_text'] or "").split("\n"):
            yield _normalize(addr_line)

        # "<post-code> <city>" or "<post-code>" or "<city>" or None
        yield self._get_city_line(fields)
        yield self._get_country(fields)


format_ldap_postal_address = _LdapPostalAddress()
"""
Formatter for LDAP postalAddress fields.

This formatter takes an address from our :class:`AddressSelector`
and formats it according to RFC-4519 (oid 2.5.4.16).

Example: ``Pb. 123$123 Example Street$1234 City$Country``
"""


class _LdapStreetAddress(_AddressFormatter):
    """ Format a street field for LDAP. """
    separator = ", "

    def _get_values(self, fields):
        # ignore p_o_box
        for addr_line in (fields['address_text'] or "").split("\n"):
            yield _normalize(addr_line)
        yield self._get_city_line(fields)
        yield self._get_country(fields)


format_ldap_street_address = _LdapStreetAddress()
"""
Formatter for LDAP street fields.

This formatter takes an address from our :class:`AddressSelector`
and formats it according to RFC-4519 (oid 2.5.4.9).

.. note::
   For legacy reasons, this includes the full address, and not just
   street name and house number.

Example: ``123 Example Street, 1234 City, Country``
"""


class AddressGetter(object):
    """
    Helper for setting up address selection and formatting.

    Example:
    ::

        shared_cache = AddressCache(
            database,
            address_types=(
                const.address_street,
                const.address_post,
            ),
        )
        get_street_addr = AddressGetter(
            shared_cache,
            AddressSelector(
                self.const.address_street,
                self.const.get_system_lookup_order(),
            ),
            format_ldap_street_address,
        )

        print(get_street_addr(ou.entity_id))
    """

    def __init__(self, cache, selector, formatter):
        self.cache = cache
        self.select_address = selector
        self.format_address = formatter

    def __call__(self, entity_id):
        addrs = self.cache.get(int(entity_id))
        addr = self.select_address(addrs or [])
        if addr:
            return self.format_address(addr)
        return None
