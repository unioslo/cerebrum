# -*- coding: utf-8 -*-
#
# Copyright 2022-2026 University of Oslo, Norway
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
Parse and normalize Orgreg data.

This module can be used to ensure that we have a *sane* response from Orgreg,
and data that is easy to work with.

This is typically done using the :func:`.parse_org_unit` function, which will:

Validate data
    E.g. require ``ouId`` to be non-empty, require date fields to be valid
    ISO-8601 formatted strings (if given).

Normalize data
    E.g. turn ISO-8601 date strings into :class:`datetime.date` objects,
    normalize text data to Unicode NFC.

Filter data
    Filter out unwanted data fields, e.g. org unit ``order`` and ``startDate``

Re-organize data
    Ensure that objects (addresses, external ids, localized names) follow a
    given structure.

The input data is typically a :class:`dict` with the JSON-response from
:meth:`.client.OrgregClient.get_org_unit`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.utils import date as date_utils
from Cerebrum.utils import textnorm


def parse_orgreg_date(value, allow_empty=False):
    """ Parse and normalize a date string from Orgreg. """
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty date')
    return date_utils.parse_date(value)


def normalize_text(value, allow_empty=False):
    r"""
    Normalize plaintext strings.

    >>> normalize_text("a\N{COMBINED RING ABOVE}")
    '\xc5'  # "\N{LATIN SMALL LETTER A WITH RING ABOVE}"
    """
    if not value or not value.strip():
        if allow_empty:
            return None
        else:
            raise ValueError('empty text')
    return textnorm.normalize(value.strip())


def parse_orgreg_address(d):
    """
    Parse and normalize an address object from Orgreg.

    Examples:

    >>> parse_orgreg_address({})  # None
    >>> parse_orgreg_address({'street': ''})  # None
    >>> parse_orgreg_address({'street': 'foo'})
    {'street': 'foo', 'city': None, ...}
    """
    if not d:
        return None
    addr = {
        'street': normalize_text(d.get('street'), allow_empty=True),
        'extended': normalize_text(d.get('extended'), allow_empty=True),
        'postalCode': normalize_text(d.get('postalCode'), allow_empty=True),
        'city': normalize_text(d.get('city'), allow_empty=True),
        # state/province is not really used in Cerebrum
        # 'province': normalize_text(d.get('stateOrProvinceName'),
        #                            allow_empty=True),
        'country': normalize_text(d.get('country'), allow_empty=True),
    }
    if not any(addr.values()):
        return None
    return addr


LANGUAGE_MAP = {
    'eng': 'en',
    'nno': 'nn',
    'nob': 'nb',
}
"""
Language mapping for localized data.

Maps Orgreg three-letter language code to Cerebrum two-letter language code
(ISO-369-2 to ISO-369-1).

We only need to include languages we want available to the mapper function,
:func:`.parse_localized_data`.  Any language missing from this will be ignored.
"""


def parse_localized_data(d):
    """
    Parse and normalize a localized text object from Orgreg.

    >>> parse_localized_data(None)
    {'nb': None, 'nn': None, 'en': None}

    >>> parse_localized_data({'nob': 'hei', 'eng': 'hi',
    ...                       'foo': 'bar', 'baz': 'quux'})
    {'no': 'hei', 'en': 'hi', 'nn': None}
    """
    d = d or {}
    known = {}
    for long, short in LANGUAGE_MAP.items():
        known[short] = normalize_text(d.get(long), allow_empty=True)
    return known


def parse_external_id(d):
    """ Parse and normalize an external id object from Orgreg. """
    return {
        'type': normalize_text(d['type']),
        'sourceSystem': normalize_text(d['sourceSystem']),
        'value': normalize_text(d['value']),
    }


def parse_org_unit(d):
    """ Parse and normalize an org unit object from Orgreg. """
    return {
        'ouId': int(d['ouId']),
        'hierarchy': normalize_text(d['hierarchy']),
        # Parent may be set to 0 for root org units, or just missing.  Let's
        # make that a bit more explicit by setting `None` to represent "no
        # parent":
        'parent': (int(d['parent']) if 'parent' in d else None) or None,
        'children': tuple(int(c) for c in d['children']),

        # identifiers and other metadata
        'externalKeys': tuple(parse_external_id(i) for i in d['externalKeys']),
        'note': normalize_text(d.get('note'), allow_empty=True),
        'tags': tuple(normalize_text(t) for t in d['tags']),
        'validFrom': parse_orgreg_date(d['validFrom']),
        'validTo': parse_orgreg_date(d.get('validTo'), allow_empty=True),

        # contact info
        'email': normalize_text(d.get('email'), allow_empty=True),
        'fax': normalize_text(d.get('fax'), allow_empty=True),
        'phone': normalize_text(d.get('phone'), allow_empty=True),

        # addresses - either non-empty dicts or None
        'postalAddress': parse_orgreg_address(d.get('postalAddress')),
        'visitAddress': parse_orgreg_address(d.get('visitAddress')),

        # localized data / names - always non-empty dicts with keys en/nb/nn
        'homepage': parse_localized_data(d.get('homepage')),
        'acronym': parse_localized_data(d.get('acronym')),
        'shortName': parse_localized_data(d.get('shortName')),
        'name': parse_localized_data(d.get('name')),
        'longName': parse_localized_data(d.get('longName')),
    }
